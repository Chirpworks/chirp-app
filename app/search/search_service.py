import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, cast, Float

from app import db
from app.models.semantic_document import SemanticDocument
from app.external.llm.open_ai.embeddings import EmbeddingsClient
from pgvector.sqlalchemy import Vector


logger = logging.getLogger(__name__)


class SemanticSearchService:
    """Vector similarity search over `semantic_documents` with ACL filters.

    - Agency filter is mandatory.
    - Optional seller_id and type filters.
    - Orders by L2 distance (embedding <-> query_embedding).
    """

    def __init__(self, embeddings: Optional[EmbeddingsClient] = None):
        self.embeddings = embeddings or EmbeddingsClient()

    def search(
        self,
        *,
        query: str,
        agency_id: str,
        k: int = 8,
        types: Optional[List[str]] = None,
        seller_id: Optional[str] = None,
        start: Optional[Any] = None,
        end: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        if not query or not agency_id:
            return []

        # Embed query
        q_vec = self.embeddings.embed_texts([query])[0]

        # Bind parameter with pgvector type for distance computation
        q_param = bindparam("qvec", value=q_vec, type_=Vector(1536))
        distance_expr = cast(SemanticDocument.embedding.op('<->')(q_param), Float)

        qry = (
            db.session.query(
                SemanticDocument.id,
                SemanticDocument.type,
                SemanticDocument.text,
                SemanticDocument.meta,
                SemanticDocument.agency_id,
                SemanticDocument.meeting_id,
                SemanticDocument.buyer_id,
                SemanticDocument.product_id,
                SemanticDocument.seller_id,
                distance_expr.label('distance'),
            )
            .filter(SemanticDocument.agency_id == agency_id)
        )

        if types:
            qry = qry.filter(SemanticDocument.type.in_(types))

        if seller_id:
            qry = qry.filter(SemanticDocument.seller_id == seller_id)

        # Optional date filter: use created_at when provided
        if start is not None:
            try:
                from datetime import datetime
                s_val = start if isinstance(start, datetime) else datetime.fromisoformat(str(start))
                qry = qry.filter(SemanticDocument.created_at >= s_val)
            except Exception:
                pass
        if end is not None:
            try:
                from datetime import datetime
                e_val = end if isinstance(end, datetime) else datetime.fromisoformat(str(end))
                qry = qry.filter(SemanticDocument.created_at <= e_val)
            except Exception:
                pass

        results = (
            qry.params(qvec=q_vec)
            .order_by(distance_expr.asc())
            .limit(max(1, min(100, int(k))))
            .all()
        )

        items: List[Dict[str, Any]] = []
        for r in results:
            items.append(
                {
                    'id': str(r.id),
                    'type': r.type,
                    'text': r.text,
                    'meta': r.meta,
                    'agency_id': str(r.agency_id) if r.agency_id else None,
                    'meeting_id': str(r.meeting_id) if r.meeting_id else None,
                    'buyer_id': str(r.buyer_id) if r.buyer_id else None,
                    'product_id': str(r.product_id) if r.product_id else None,
                    'seller_id': str(r.seller_id) if r.seller_id else None,
                    'distance': float(r.distance) if r.distance is not None else None,
                }
            )

        return items



