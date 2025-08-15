import logging
import os
from typing import Optional

from app import create_app, db
from app.models.meeting import Meeting
from app.models.buyer import Buyer
from app.models.product import Product
from app.models.action import Action
from app.search.index_service import SemanticIndexService
from app.search.index_helpers import (
    index_meeting_transcript,
    index_buyer,
    index_product,
    index_action,
    index_seller,
    index_mobile_app_call,
)
from app.models.seller import Seller
from app.models.action import Action
from app.models.product import Product
from app.models.mobile_app_calls import MobileAppCall
from concurrent.futures import ThreadPoolExecutor, as_completed


def _index_in_context(app, model_cls, obj_id, index_fn):
    with app.app_context():
        inst = db.session.get(model_cls, obj_id)
        if inst is None:
            return
        try:
            index_fn(inst)
        except Exception:
            db.session.rollback()
            raise


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill_meetings(app) -> None:
    svc = SemanticIndexService()
    meetings = Meeting.query.order_by(Meeting.start_time.asc()).all()
    logger.info("Indexing %s meetings", len(meetings))
    with ThreadPoolExecutor(max_workers=int(os.getenv("BACKFILL_WORKERS", "4"))) as ex:
        futures = []
        from app.services.meeting_service import MeetingService
        for m in meetings:
            m_id = str(m.id)
            futures.append(ex.submit(
                _index_in_context, app, Meeting, m_id,
                lambda inst: (MeetingService._index_meeting_structured(inst), index_meeting_transcript(inst))
            ))
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                logger.error("Failed indexing meeting: %s", e)


def backfill_buyers(app) -> None:
    buyers = Buyer.query.all()
    logger.info("Indexing %s buyers", len(buyers))
    with ThreadPoolExecutor(max_workers=int(os.getenv("BACKFILL_WORKERS", "4"))) as ex:
        futures = [ex.submit(_index_in_context, app, Buyer, str(b.id), index_buyer) for b in buyers]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                logger.error("Failed to index buyer: %s", e)


def backfill_products(app) -> None:
    products = Product.query.all()
    logger.info("Indexing %s products", len(products))
    with ThreadPoolExecutor(max_workers=int(os.getenv("BACKFILL_WORKERS", "4"))) as ex:
        futures = [ex.submit(_index_in_context, app, Product, str(p.id), index_product) for p in products]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                logger.error("Failed to index product: %s", e)


def backfill_actions(app) -> None:
    actions = Action.query.all()
    logger.info("Indexing %s actions", len(actions))
    with ThreadPoolExecutor(max_workers=int(os.getenv("BACKFILL_WORKERS", "4"))) as ex:
        futures = [ex.submit(_index_in_context, app, Action, str(a.id), index_action) for a in actions]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                logger.error("Failed to index action: %s", e)

def backfill_sellers(app) -> None:
    sellers = Seller.query.all()
    logger.info("Indexing %s sellers", len(sellers))
    with ThreadPoolExecutor(max_workers=int(os.getenv("BACKFILL_WORKERS", "4"))) as ex:
        futures = [ex.submit(_index_in_context, app, Seller, str(s.id), index_seller) for s in sellers]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                logger.error("Failed to index seller: %s", e)

def backfill_mobile_calls(app) -> None:
    calls = MobileAppCall.query.all()
    logger.info("Indexing %s mobile app calls", len(calls))
    with ThreadPoolExecutor(max_workers=int(os.getenv("BACKFILL_WORKERS", "4"))) as ex:
        futures = [ex.submit(_index_in_context, app, MobileAppCall, str(c.id), index_mobile_app_call) for c in calls]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                logger.error("Failed to index mobile call: %s", e)


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        if os.getenv("SEMANTIC_INDEXING_ENABLED", "false").lower() not in ("1", "true", "yes", "on"):
            logger.info("SEMANTIC_INDEXING_ENABLED is not set; skipping backfill")
        else:
            # Re-run meetings as well (idempotent upserts)
            backfill_meetings(app)
            backfill_buyers(app)
            backfill_products(app)
            backfill_actions(app)
            backfill_sellers(app)
            backfill_mobile_calls(app)
        db.session.commit()
        logger.info("Backfill complete")


