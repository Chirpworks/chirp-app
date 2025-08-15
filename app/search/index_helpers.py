import json
import logging
from typing import Optional

from app import db
from app.models.semantic_document import SemanticDocument
from app.search.index_service import SemanticIndexService


logger = logging.getLogger(__name__)


def _to_text(val) -> str:
    if val is None:
        return ''
    if isinstance(val, (list, dict)):
        try:
            return json.dumps(val, ensure_ascii=False)
        except Exception:
            return str(val)
    return str(val)


def index_meeting_transcript(meeting) -> None:
    try:
        transcript = getattr(meeting, 'transcription', None)
        if not transcript:
            return
        # Skip if any transcript chunks already exist for this meeting
        exists = (
            db.session.query(SemanticDocument.id)
            .filter(
                SemanticDocument.type == 'meeting.transcript',
                SemanticDocument.meeting_id == str(getattr(meeting, 'id', '')),
            )
            .first()
        )
        if exists:
            return
        svc = SemanticIndexService()
        chunks = svc.chunk_text(transcript, target_tokens=800, overlap_ratio=0.15)
        agency_id = str(getattr(meeting.seller, 'agency_id', getattr(meeting.buyer, 'agency_id', '')))
        meta = {
            'seller_id': str(getattr(meeting, 'seller_id', '')),
            'buyer_id': str(getattr(meeting, 'buyer_id', '')),
            'direction': getattr(meeting, 'direction', None),
            'start_time': getattr(meeting, 'start_time', None).isoformat() if getattr(meeting, 'start_time', None) else None,
        }
        svc.upsert_documents(
            doc_type='meeting.transcript',
            entity_id=str(meeting.id),
            agency_id=agency_id,
            text_chunks=chunks,
            meta=meta,
            entity_refs={
                'meeting_id': str(meeting.id),
                'buyer_id': str(getattr(meeting, 'buyer_id', '')),
                'product_id': None,
                'seller_id': str(getattr(meeting, 'seller_id', '')),
            },
        )
    except Exception as e:
        logger.error(f"Failed to index meeting transcript {getattr(meeting, 'id', None)}: {e}")


def index_meeting_key_points(meeting) -> None:
    try:
        bullets = []
        summary = getattr(meeting, 'summary', None)
        if isinstance(summary, list):
            bullets = summary
        elif isinstance(summary, dict) and summary.get('bullets'):
            bullets = summary.get('bullets') or []
        if not bullets:
            return
        svc = SemanticIndexService()
        agency_id = str(getattr(meeting.seller, 'agency_id', getattr(meeting.buyer, 'agency_id', '')))
        meta = {
            'intent': 'summary',
            'seller_id': str(getattr(meeting, 'seller_id', '')),
            'buyer_id': str(getattr(meeting, 'buyer_id', '')),
            'start_time': getattr(meeting, 'start_time', None).isoformat() if getattr(meeting, 'start_time', None) else None,
        }
        text_chunks = [str(b) for b in bullets if b]
        svc.upsert_documents(
            doc_type='meeting.key_point',
            entity_id=str(meeting.id),
            agency_id=agency_id,
            text_chunks=text_chunks,
            meta=meta,
            entity_refs={'meeting_id': str(meeting.id), 'buyer_id': str(getattr(meeting, 'buyer_id', '')), 'product_id': None, 'seller_id': str(getattr(meeting, 'seller_id', ''))},
        )
    except Exception as e:
        logger.error(f"Failed to index meeting key points {getattr(meeting, 'id', None)}: {e}")


def index_meeting_qa(meeting) -> None:
    try:
        pairs = getattr(meeting, 'qa_pairs', None) or []
        if not isinstance(pairs, list) or not pairs:
            return
        svc = SemanticIndexService()
        agency_id = str(getattr(meeting.seller, 'agency_id', getattr(meeting.buyer, 'agency_id', '')))
        meta_common = {
            'intent': 'answer',
            'seller_id': str(getattr(meeting, 'seller_id', '')),
            'buyer_id': str(getattr(meeting, 'buyer_id', '')),
        }
        text_chunks = []
        for p in pairs:
            q = (p.get('question') or '').strip()
            a = (p.get('answer') or '').strip()
            if not (q and a):
                continue
            text_chunks.append(f"Q: {q}\nA: {a}")
        if not text_chunks:
            return
        svc.upsert_documents(
            doc_type='meeting.qa',
            entity_id=str(meeting.id),
            agency_id=agency_id,
            text_chunks=text_chunks,
            meta=meta_common,
            entity_refs={'meeting_id': str(meeting.id), 'buyer_id': str(getattr(meeting, 'buyer_id', '')), 'product_id': None, 'seller_id': str(getattr(meeting, 'seller_id', ''))},
        )
    except Exception as e:
        logger.error(f"Failed to index meeting QA {getattr(meeting, 'id', None)}: {e}")


def index_meeting_facts(meeting) -> None:
    try:
        facts = getattr(meeting, 'facts', None) or []
        if not isinstance(facts, list) or not facts:
            return
        svc = SemanticIndexService()
        agency_id = str(getattr(meeting.seller, 'agency_id', getattr(meeting.buyer, 'agency_id', '')))
        meta = {
            'intent': 'fact',
            'seller_id': str(getattr(meeting, 'seller_id', '')),
            'buyer_id': str(getattr(meeting, 'buyer_id', '')),
        }
        text_chunks = []
        for f in facts:
            s = (f.get('subject') or '').strip()
            p = (f.get('predicate') or '').strip()
            o = (f.get('object') or '').strip()
            if not (s and p and o):
                continue
            text_chunks.append(f"{s} —{p}→ {o}")
        if not text_chunks:
            return
        svc.upsert_documents(
            doc_type='meeting.fact',
            entity_id=str(meeting.id),
            agency_id=agency_id,
            text_chunks=text_chunks,
            meta=meta,
            entity_refs={'meeting_id': str(meeting.id), 'buyer_id': str(getattr(meeting, 'buyer_id', '')), 'product_id': None, 'seller_id': str(getattr(meeting, 'seller_id', ''))},
        )
    except Exception as e:
        logger.error(f"Failed to index meeting facts {getattr(meeting, 'id', None)}: {e}")
def index_buyer(buyer) -> None:
    try:
        svc = SemanticIndexService()
        doc_id = svc._build_doc_id('buyer.profile', str(buyer.id), 0)
        if db.session.get(SemanticDocument, doc_id):
            return
        text = "\n".join(filter(None, [
            f"Name: {_to_text(getattr(buyer, 'name', None))}",
            f"Email: {_to_text(getattr(buyer, 'email', None))}",
            f"Phone: {_to_text(getattr(buyer, 'phone', None))}",
            f"Company: {_to_text(getattr(buyer, 'company_name', None))}",
            f"Tags: {_to_text(getattr(buyer, 'tags', None))}",
            f"Requirements: {_to_text(getattr(buyer, 'requirements', None))}",
            f"Key Highlights: {_to_text(getattr(buyer, 'key_highlights', None))}",
            f"Products Discussed: {_to_text(getattr(buyer, 'products_discussed', None))}",
            f"Relationship Progression: {_to_text(getattr(buyer, 'relationship_progression', None))}",
            f"Risks: {_to_text(getattr(buyer, 'risks', None))}",
        ]))
        svc.upsert_documents(
            doc_type='buyer.profile',
            entity_id=str(buyer.id),
            agency_id=str(getattr(buyer, 'agency_id', '')),
            text_chunks=[text],
            meta={},
            entity_refs={'buyer_id': str(buyer.id), 'meeting_id': None, 'product_id': None, 'seller_id': None},
        )
    except Exception as e:
        logger.error(f"Failed to index buyer {getattr(buyer, 'id', None)}: {e}")


def index_product(product) -> None:
    try:
        svc = SemanticIndexService()
        doc_id = svc._build_doc_id('product.catalog', str(product.id), 0)
        if db.session.get(SemanticDocument, doc_id):
            return
        text = "\n".join(filter(None, [
            f"Name: {_to_text(getattr(product, 'name', None))}",
            f"Description: {_to_text(getattr(product, 'description', None))}",
            f"Features: {_to_text(getattr(product, 'features', None))}",
        ]))
        svc.upsert_documents(
            doc_type='product.catalog',
            entity_id=str(product.id),
            agency_id=str(getattr(product, 'agency_id', '')),
            text_chunks=[text],
            meta={},
            entity_refs={'product_id': str(product.id), 'meeting_id': None, 'buyer_id': None, 'seller_id': None},
        )
    except Exception as e:
        logger.error(f"Failed to index product {getattr(product, 'id', None)}: {e}")


def index_action(action) -> None:
    try:
        svc = SemanticIndexService()
        doc_id = svc._build_doc_id('action.item', str(action.id), 0)
        if db.session.get(SemanticDocument, doc_id):
            return
        text = "\n".join(filter(None, [
            f"Title: {_to_text(getattr(action, 'title', None))}",
            f"Status: {_to_text(getattr(action, 'status', None))}",
            f"Due Date: {_to_text(getattr(action, 'due_date', None))}",
            f"Description: {_to_text(getattr(action, 'description', None))}",
            f"Reasoning: {_to_text(getattr(action, 'reasoning', None))}",
            f"Signals: {_to_text(getattr(action, 'signals', None))}",
        ]))
        # derive agency from meeting.seller or buyer
        agency_id = None
        try:
            agency_id = str(getattr(action.meeting.seller, 'agency_id', None)) or str(getattr(action.buyer, 'agency_id', None))
        except Exception:
            pass
        if not agency_id:
            return
        svc.upsert_documents(
            doc_type='action.item',
            entity_id=str(action.id),
            agency_id=agency_id,
            text_chunks=[text],
            meta={},
            entity_refs={
                'meeting_id': str(getattr(action, 'meeting_id', '')),
                'buyer_id': str(getattr(action, 'buyer_id', '')),
                'seller_id': str(getattr(action, 'seller_id', '')),
                'product_id': None,
            },
        )
    except Exception as e:
        logger.error(f"Failed to index action {getattr(action, 'id', None)}: {e}")


def index_seller(seller) -> None:
    try:
        svc = SemanticIndexService()
        doc_id = svc._build_doc_id('seller.profile', str(seller.id), 0)
        if db.session.get(SemanticDocument, doc_id):
            return
        text = "\n".join(filter(None, [
            f"Name: {_to_text(getattr(seller, 'name', None))}",
            f"Email: {_to_text(getattr(seller, 'email', None))}",
            f"Phone: {_to_text(getattr(seller, 'phone', None))}",
            f"Role: {_to_text(getattr(seller, 'role', None))}",
        ]))
        svc.upsert_documents(
            doc_type='seller.profile',
            entity_id=str(seller.id),
            agency_id=str(getattr(seller, 'agency_id', '')),
            text_chunks=[text],
            meta={},
            entity_refs={'seller_id': str(seller.id), 'meeting_id': None, 'buyer_id': None, 'product_id': None},
        )
    except Exception as e:
        logger.error(f"Failed to index seller {getattr(seller, 'id', None)}: {e}")


def index_mobile_app_call(call) -> None:
    try:
        svc = SemanticIndexService()
        doc_id = svc._build_doc_id('mobile.call', str(call.id), 0)
        if db.session.get(SemanticDocument, doc_id):
            return
        text = "\n".join(filter(None, [
            f"Call Type: {_to_text(getattr(call, 'call_type', None))}",
            f"Status: {_to_text(getattr(call, 'status', None))}",
            f"Start Time: {_to_text(getattr(call, 'start_time', None))}",
            f"End Time: {_to_text(getattr(call, 'end_time', None))}",
            f"Duration: {_to_text(getattr(call, 'duration', None))}",
            f"Buyer Number: {_to_text(getattr(call, 'buyer_number', None))}",
            f"Seller Number: {_to_text(getattr(call, 'seller_number', None))}",
        ]))
        # agency via call.user.agency_id
        try:
            agency_id = str(getattr(call.user, 'agency_id', ''))
            seller_id = str(getattr(call.user, 'id', ''))
        except Exception:
            return
        svc.upsert_documents(
            doc_type='mobile.call',
            entity_id=str(call.id),
            agency_id=agency_id,
            text_chunks=[text],
            meta={},
            entity_refs={'seller_id': seller_id, 'meeting_id': None, 'buyer_id': None, 'product_id': None},
        )
    except Exception as e:
        logger.error(f"Failed to index mobile call {getattr(call, 'id', None)}: {e}")


