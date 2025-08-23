import logging
import os
from typing import List, Optional

from sqlalchemy import delete

from app import db
from app.models.semantic_document import SemanticDocument
from app.external.llm.open_ai.embeddings import EmbeddingsClient


logger = logging.getLogger(__name__)


class SemanticIndexService:
    """Upsert and delete semantic documents with embeddings.

    Update strategy:
    - Deterministic document IDs: use (type, entity_id, chunk_index) to derive a stable UUID so updates
      overwrite prior vectors instead of duplicating.
    - On entity update, re-generate chunks and upsert all; delete any surplus chunks that no longer exist.
    """

    def __init__(self, embeddings: Optional[EmbeddingsClient] = None):
        self.embeddings = embeddings or EmbeddingsClient()

    @staticmethod
    def _build_doc_id(doc_type: str, entity_id: str, chunk_index: int) -> str:
        import uuid
        ns = uuid.uuid5(uuid.NAMESPACE_DNS, f"semantic:{doc_type}")
        return str(uuid.uuid5(ns, f"{entity_id}:{chunk_index}"))

    def upsert_documents(
        self,
        *,
        doc_type: str,
        entity_id: str,
        agency_id: str,
        text_chunks: List[str],
        meta: dict,
        entity_refs: dict,
    ) -> List[str]:
        # Feature flag guard: skip entirely if disabled
        if os.getenv("SEMANTIC_INDEXING_ENABLED", "false").lower() not in ("1", "true", "yes", "on"):
            logger.info("Semantic indexing disabled; skipping upsert for %s:%s", doc_type, entity_id)
            return []

        if not text_chunks:
            return []

        vectors = self.embeddings.embed_texts(text_chunks)
        stored_ids: List[str] = []

        for idx, (text, vector) in enumerate(zip(text_chunks, vectors)):
            doc_id = self._build_doc_id(doc_type, entity_id, idx)
            stored_ids.append(doc_id)

            existing: Optional[SemanticDocument] = db.session.get(SemanticDocument, doc_id)
            if existing is None:
                row = SemanticDocument(
                    id=doc_id,
                    type=doc_type,
                    text=text,
                    meta=meta,
                    agency_id=agency_id,
                    embedding=vector,
                    meeting_id=entity_refs.get('meeting_id'),
                    buyer_id=entity_refs.get('buyer_id'),
                    product_id=entity_refs.get('product_id'),
                    seller_id=entity_refs.get('seller_id'),
                )
                db.session.add(row)
            else:
                existing.text = text
                existing.meta = meta
                existing.embedding = vector
                existing.agency_id = agency_id
                existing.meeting_id = entity_refs.get('meeting_id')
                existing.buyer_id = entity_refs.get('buyer_id')
                existing.product_id = entity_refs.get('product_id')
                existing.seller_id = entity_refs.get('seller_id')

        db.session.flush()

        self._delete_stale_chunks(
            doc_type=doc_type,
            entity_id=entity_id,
            entity_refs=entity_refs,
            keep_ids=stored_ids,
        )

        db.session.commit()
        logger.info("Upserted %s semantic docs for %s:%s", len(stored_ids), doc_type, entity_id)
        return stored_ids

    def _delete_stale_chunks(self, *, doc_type: str, entity_id: str, entity_refs: dict, keep_ids: List[str]) -> None:
        """Delete obsolete chunks ONLY for this entity and type.

        We filter by the specific entity reference column to avoid deleting other entities' docs.
        """
        q = delete(SemanticDocument).where(SemanticDocument.type == doc_type)
        # Narrow by entity ref column
        if doc_type.startswith("meeting"):
            q = q.where(SemanticDocument.meeting_id == entity_refs.get('meeting_id'))
        elif doc_type.startswith("buyer"):
            q = q.where(SemanticDocument.buyer_id == entity_refs.get('buyer_id'))
        elif doc_type.startswith("product"):
            q = q.where(SemanticDocument.product_id == entity_refs.get('product_id'))
        elif doc_type.startswith("seller"):
            q = q.where(SemanticDocument.seller_id == entity_refs.get('seller_id'))
        # Keep currently written ids
        q = q.where(~SemanticDocument.id.in_(keep_ids))
        db.session.execute(q)

    @staticmethod
    def chunk_text(text: str, *, target_tokens: int = 800, overlap_ratio: float = 0.15) -> List[str]:
        if not text:
            return []
        words = text.split()
        words_per_chunk = max(50, int(target_tokens * 1.3))
        overlap = int(words_per_chunk * overlap_ratio)
        chunks: List[str] = []
        i = 0
        while i < len(words):
            chunk_words = words[i:i + words_per_chunk]
            if not chunk_words:
                break
            chunks.append(' '.join(chunk_words))
            i += max(1, words_per_chunk - overlap)
        return chunks


