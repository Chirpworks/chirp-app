import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, or_, cast, String, func, desc

from app import db
from app.models.meeting import Meeting
from app.models.seller import Seller
from app.models.mobile_app_calls import MobileAppCall
from app.models.product import Product
from app.constants import MobileAppCallStatus


logger = logging.getLogger(__name__)


class AnalyticsTool:
    """Programmatic analytics helpers reused by the answer flow.

    All methods are ACL-scoped by agency_id and accept explicit date ranges.
    Returned payloads are structured for direct inclusion in the answer JSON.
    """

    @staticmethod
    def _seller_ids_for_agency(agency_id: str) -> List[str]:
        rows = db.session.query(Seller.id).filter(Seller.agency_id == agency_id).all()
        return [str(r.id) for r in rows]

    @staticmethod
    def _date_range(start: Optional[datetime], end: Optional[datetime]) -> Tuple[Optional[datetime], Optional[datetime]]:
        # Default window: current month start to now, plus include last month by setting start to last month start
        if start or end:
            return start, end
        from dateutil.relativedelta import relativedelta
        now = datetime.now().astimezone()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (current_month_start - relativedelta(months=1)).replace(day=1)
        return last_month_start, now

    @classmethod
    def count_total_calls(
        cls,
        *,
        agency_id: str,
        start: Optional[datetime],
        end: Optional[datetime],
    ) -> Dict[str, Any]:
        seller_ids = cls._seller_ids_for_agency(agency_id)
        if not seller_ids:
            return {
                "answer": "No sellers found for this agency.",
                "sources": [{"type": "analytics", "reason": "empty_agency"}],
            }

        start_dt, end_dt = cls._date_range(start, end)

        meeting_filters = [Meeting.seller_id.in_(seller_ids)]
        if start_dt:
            meeting_filters.append(Meeting.start_time >= start_dt)
        if end_dt:
            meeting_filters.append(Meeting.start_time <= end_dt)

        incoming_answered = db.session.query(func.count(Meeting.id)).filter(
            and_(*(meeting_filters + [Meeting.direction == "incoming"]))
        ).scalar() or 0

        outgoing_answered = db.session.query(func.count(Meeting.id)).filter(
            and_(*(meeting_filters + [Meeting.direction == "outgoing"]))
        ).scalar() or 0

        mac_filters = [MobileAppCall.user_id.in_(seller_ids)]
        if start_dt:
            mac_filters.append(MobileAppCall.start_time >= start_dt)
        if end_dt:
            mac_filters.append(MobileAppCall.start_time <= end_dt)

        outgoing_unanswered = db.session.query(func.count(MobileAppCall.id)).filter(
            and_(*mac_filters, MobileAppCall.call_type == "outgoing", MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
        ).scalar() or 0

        incoming_unanswered = db.session.query(func.count(MobileAppCall.id)).filter(
            and_(*mac_filters, MobileAppCall.call_type == "incoming", MobileAppCall.status.in_([MobileAppCallStatus.MISSED.value, MobileAppCallStatus.REJECTED.value]))
        ).scalar() or 0

        total_calls = incoming_answered + outgoing_answered + outgoing_unanswered + incoming_unanswered

        # Natural-language summary
        human = (
            f"The team made {total_calls} calls between "
            f"{start_dt.date() if start_dt else 'N/A'} and {end_dt.date() if end_dt else 'N/A'}."
        )

        return {
            "answer": human,
            "sources": [
                {
                    "type": "analytics",
                    "metric": "total_calls",
                    "components": {
                        "incoming_answered": incoming_answered,
                        "outgoing_answered": outgoing_answered,
                        "outgoing_unanswered": outgoing_unanswered,
                        "incoming_unanswered": incoming_unanswered,
                    },
                    "date_range": {
                        "start": start_dt.isoformat() if start_dt else None,
                        "end": end_dt.isoformat() if end_dt else None,
                    },
                }
            ],
        }

    @classmethod
    def count_calls(
        cls,
        *,
        agency_id: str,
        start: Optional[datetime],
        end: Optional[datetime],
        direction: Optional[str],  # "incoming" | "outgoing" | None
        answered: Optional[str],   # "answered" | "unanswered" | None
    ) -> Dict[str, Any]:
        """Flexible call counting with direction and answered/unanswered filters."""
        seller_ids = cls._seller_ids_for_agency(agency_id)
        start_dt, end_dt = cls._date_range(start, end)

        # Meetings = answered
        meeting_filters = [Meeting.seller_id.in_(seller_ids)]
        if start_dt:
            meeting_filters.append(Meeting.start_time >= start_dt)
        if end_dt:
            meeting_filters.append(Meeting.start_time <= end_dt)
        if direction in ("incoming", "outgoing"):
            meeting_filters.append(Meeting.direction == direction)

        answered_count = db.session.query(func.count(Meeting.id)).filter(and_(*meeting_filters)).scalar() or 0

        # MobileAppCall = unanswered
        mac_filters = [MobileAppCall.user_id.in_(seller_ids)]
        if start_dt:
            mac_filters.append(MobileAppCall.start_time >= start_dt)
        if end_dt:
            mac_filters.append(MobileAppCall.start_time <= end_dt)
        # Unanswered logic aligned to status constants
        if direction == "incoming":
            unanswered_filter = and_(MobileAppCall.call_type == "incoming", MobileAppCall.status.in_([MobileAppCallStatus.MISSED.value, MobileAppCallStatus.REJECTED.value]))
        elif direction == "outgoing":
            unanswered_filter = and_(MobileAppCall.call_type == "outgoing", MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
        else:
            unanswered_filter = or_(
                and_(MobileAppCall.call_type == "incoming", MobileAppCall.status.in_([MobileAppCallStatus.MISSED.value, MobileAppCallStatus.REJECTED.value])),
                and_(MobileAppCall.call_type == "outgoing", MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value),
            )
        unanswered_count = db.session.query(func.count(MobileAppCall.id)).filter(and_(*mac_filters, unanswered_filter)).scalar() or 0

        if answered == "answered":
            total = answered_count
        elif answered == "unanswered":
            total = unanswered_count
        else:
            total = answered_count + unanswered_count

        # Natural-language summary
        dir_txt = f" {direction}" if direction in ("incoming", "outgoing") else ""
        qual_txt = (
            " answered" if answered == "answered" else (" unanswered" if answered == "unanswered" else "")
        )
        human = (
            f"{total}{qual_txt}{dir_txt} calls between "
            f"{start_dt.date() if start_dt else 'N/A'} and {end_dt.date() if end_dt else 'N/A'}."
        ).strip()

        return {
            "answer": human,
            "sources": [{
                "type": "analytics",
                "metric": "calls",
                "direction": direction,
                "answered": answered,
                "components": {"answered": answered_count, "unanswered": unanswered_count},
                "date_range": {"start": start_dt.isoformat() if start_dt else None, "end": end_dt.isoformat() if end_dt else None}
            }],
        }

    @classmethod
    def count_buyers(
        cls,
        *,
        agency_id: str,
        start: Optional[datetime],
        end: Optional[datetime],
        mode: str,  # "total" or "engaged"
    ) -> Dict[str, Any]:
        from app.models.buyer import Buyer
        start_dt, end_dt = cls._date_range(start, end)
        if mode == "engaged":
            # Distinct buyers who had meetings in range
            meeting_filters = [Meeting.seller_id.in_(cls._seller_ids_for_agency(agency_id))]
            if start_dt:
                meeting_filters.append(Meeting.start_time >= start_dt)
            if end_dt:
                meeting_filters.append(Meeting.start_time <= end_dt)
            q = db.session.query(func.count(func.distinct(Meeting.buyer_id))).filter(and_(*meeting_filters))
            count = q.scalar() or 0
        else:
            q = db.session.query(func.count(Buyer.id)).filter(Buyer.agency_id == agency_id)
            count = q.scalar() or 0
        human = (
            f"{count} buyers {'engaged' if mode=='engaged' else 'in your CRM'}"
            f" between {start_dt.date() if start_dt else 'N/A'} and {end_dt.date() if end_dt else 'N/A'}."
        )
        return {"answer": human, "sources": [{"type": "analytics", "metric": f"buyers_{mode}", "date_range": {"start": start_dt.isoformat() if start_dt else None, "end": end_dt.isoformat() if end_dt else None}}]}

    @classmethod
    def count_sellers(
        cls,
        *,
        agency_id: str,
        start: Optional[datetime],
        end: Optional[datetime],
        mode: str,  # "total" or "active"
    ) -> Dict[str, Any]:
        start_dt, end_dt = cls._date_range(start, end)
        if mode == "active":
            # Sellers who appear in meetings or mobile calls in range
            meeting_filters = []
            if start_dt:
                meeting_filters.append(Meeting.start_time >= start_dt)
            if end_dt:
                meeting_filters.append(Meeting.start_time <= end_dt)
            active_meeting_sellers = db.session.query(func.distinct(Meeting.seller_id)).filter(and_(*meeting_filters)).subquery()

            mac_filters = []
            if start_dt:
                mac_filters.append(MobileAppCall.start_time >= start_dt)
            if end_dt:
                mac_filters.append(MobileAppCall.start_time <= end_dt)
            active_mobile_sellers = db.session.query(func.distinct(MobileAppCall.user_id)).filter(and_(*mac_filters)).subquery()

            from app.models.seller import Seller
            count = db.session.query(func.count(func.distinct(Seller.id))).filter(
                Seller.agency_id == agency_id,
                Seller.id.in_(db.session.query(active_meeting_sellers)) | Seller.id.in_(db.session.query(active_mobile_sellers))
            ).scalar() or 0
        else:
            from app.models.seller import Seller
            count = db.session.query(func.count(Seller.id)).filter(Seller.agency_id == agency_id).scalar() or 0
        return {"answer": str(count), "sources": [{"type": "analytics", "metric": f"sellers_{mode}", "date_range": {"start": start_dt.isoformat() if start_dt else None, "end": end_dt.isoformat() if end_dt else None}}]}

    @classmethod
    def count_products(
        cls,
        *,
        agency_id: str,
        start: Optional[datetime],
        end: Optional[datetime],
        mode: str,  # "catalog" or "discussed"
    ) -> Dict[str, Any]:
        start_dt, end_dt = cls._date_range(start, end)
        if mode == "discussed":
            meeting_filters = [Meeting.seller_id.in_(cls._seller_ids_for_agency(agency_id)), Meeting.detected_products.isnot(None)]
            if start_dt:
                meeting_filters.append(Meeting.start_time >= start_dt)
            if end_dt:
                meeting_filters.append(Meeting.start_time <= end_dt)
            # Count distinct product names from detected_products JSON text
            # MVP: cast to text and count distinct values
            distinct_products = db.session.query(func.distinct(cast(Meeting.detected_products, String))).filter(and_(*meeting_filters)).all()
            count = len([d[0] for d in distinct_products if d[0]])
        else:
            count = db.session.query(func.count(Product.id)).filter(Product.agency_id == agency_id).scalar() or 0
        human = (
            f"{count} products {'discussed' if mode=='discussed' else 'in catalog'}"
            f" between {start_dt.date() if start_dt else 'N/A'} and {end_dt.date() if end_dt else 'N/A'}."
        )
        return {"answer": human, "sources": [{"type": "analytics", "metric": f"products_{mode}", "date_range": {"start": start_dt.isoformat() if start_dt else None, "end": end_dt.isoformat() if end_dt else None}}]}

    @classmethod
    def answered_rate(cls, *, agency_id: str, start: Optional[datetime], end: Optional[datetime]) -> Dict[str, Any]:
        base = cls.count_calls(agency_id=agency_id, start=start, end=end, direction=None, answered=None)
        ans = cls.count_calls(agency_id=agency_id, start=start, end=end, direction=None, answered="answered")
        total = int(base["answer"]) if str(base["answer"]).isdigit() else 0
        answered = int(ans["answer"]) if str(ans["answer"]).isdigit() else 0
        rate = round((answered / total) * 100, 2) if total > 0 else 0.0
        return {"answer": f"{rate}", "sources": [{"type": "analytics", "metric": "answered_rate", "components": {"answered": answered, "total": total}, "date_range": base["sources"][0]["date_range"]}]}

    @classmethod
    def missed_rate(cls, *, agency_id: str, start: Optional[datetime], end: Optional[datetime]) -> Dict[str, Any]:
        base = cls.count_calls(agency_id=agency_id, start=start, end=end, direction=None, answered=None)
        missed = cls.count_calls(agency_id=agency_id, start=start, end=end, direction="incoming", answered="unanswered")
        total = int(base["answer"]) if str(base["answer"]).isdigit() else 0
        missed_n = int(missed["answer"]) if str(missed["answer"]).isdigit() else 0
        rate = round((missed_n / total) * 100, 2) if total > 0 else 0.0
        return {"answer": f"{rate}", "sources": [{"type": "analytics", "metric": "missed_rate", "components": {"missed": missed_n, "total": total}, "date_range": base["sources"][0]["date_range"]}]}

    @classmethod
    def avg_call_duration(cls, *, agency_id: str, start: Optional[datetime], end: Optional[datetime], direction: Optional[str] = None) -> Dict[str, Any]:
        start_dt, end_dt = cls._date_range(start, end)
        # meetings duration
        q_m = db.session.query(func.avg(func.extract('epoch', Meeting.end_time - Meeting.start_time))).filter(Meeting.seller_id.in_(cls._seller_ids_for_agency(agency_id)))
        if start_dt:
            q_m = q_m.filter(Meeting.start_time >= start_dt)
        if end_dt:
            q_m = q_m.filter(Meeting.start_time <= end_dt)
        if direction in ("incoming", "outgoing"):
            q_m = q_m.filter(Meeting.direction == direction)
        avg_meeting_sec = q_m.scalar() or 0
        # mobile app nominal duration field
        q_c = db.session.query(func.avg(MobileAppCall.duration)).filter(MobileAppCall.user_id.in_(cls._seller_ids_for_agency(agency_id)))
        if start_dt:
            q_c = q_c.filter(MobileAppCall.start_time >= start_dt)
        if end_dt:
            q_c = q_c.filter(MobileAppCall.start_time <= end_dt)
        if direction in ("incoming", "outgoing"):
            q_c = q_c.filter(MobileAppCall.call_type == direction)
        avg_mobile_sec = q_c.scalar() or 0
        # prefer meeting avg if available
        avg_sec = float(avg_meeting_sec) if avg_meeting_sec else float(avg_mobile_sec or 0)
        dir_txt = f" for {direction} calls" if direction in ("incoming", "outgoing") else ""
        human = (
            f"Average call duration{dir_txt} between {start_dt.date() if start_dt else 'N/A'} and {end_dt.date() if end_dt else 'N/A'} is {round(avg_sec, 2)} seconds."
        )
        return {"answer": human, "sources": [{"type": "analytics", "metric": "avg_call_duration_sec", "components": {"meetings_avg_sec": float(avg_meeting_sec or 0), "mobile_avg_sec": float(avg_mobile_sec or 0)}, "date_range": {"start": start_dt.isoformat() if start_dt else None, "end": end_dt.isoformat() if end_dt else None}}]}

    @classmethod
    def top_sellers_by_calls(cls, *, agency_id: str, start: Optional[datetime], end: Optional[datetime], limit: int = 5, metric: str = "total") -> Dict[str, Any]:
        start_dt, end_dt = cls._date_range(start, end)
        # total = answered(meetings) + unanswered(mobile)
        mf = []
        if start_dt:
            mf.append(Meeting.start_time >= start_dt)
        if end_dt:
            mf.append(Meeting.start_time <= end_dt)
        m_counts = db.session.query(Meeting.seller_id, func.count(Meeting.id).label('cnt')).filter(and_(*mf)).group_by(Meeting.seller_id).subquery()

        cf = []
        if start_dt:
            cf.append(MobileAppCall.start_time >= start_dt)
        if end_dt:
            cf.append(MobileAppCall.start_time <= end_dt)
        c_counts = db.session.query(MobileAppCall.user_id, func.count(MobileAppCall.id).label('cnt')).filter(and_(*cf)).group_by(MobileAppCall.user_id).subquery()

        if metric == "answered":
            join_counts = db.session.query(Seller.id, Seller.name, func.coalesce(m_counts.c.cnt, 0).label('score')).outerjoin(m_counts, m_counts.c.seller_id == Seller.id)
        else:
            join_counts = db.session.query(Seller.id, Seller.name, (func.coalesce(m_counts.c.cnt, 0) + func.coalesce(c_counts.c.cnt, 0)).label('score')).outerjoin(m_counts, m_counts.c.seller_id == Seller.id).outerjoin(c_counts, c_counts.c.user_id == Seller.id)

        rows = join_counts.filter(Seller.agency_id == agency_id).order_by(desc('score')).limit(limit).all()
        items = [{"seller_id": str(r.id), "seller_name": r.name, "score": int(getattr(r, 'score') or 0)} for r in rows]
        # concise NL summary
        summary = ", ".join([f"{i+1}) {it['seller_name']} ({it['score']})" for i, it in enumerate(items)]) or "No data"
        nl = f"Top {limit} sellers by {metric}: {summary}."
        return {"answer": nl, "sources": [{"type": "analytics", "metric": f"top_sellers_{metric}", "limit": limit, "items": items, "date_range": {"start": start_dt.isoformat() if start_dt else None, "end": end_dt.isoformat() if end_dt else None}}]}

    @classmethod
    def top_products_discussed(cls, *, agency_id: str, start: Optional[datetime], end: Optional[datetime], limit: int = 5) -> Dict[str, Any]:
        start_dt, end_dt = cls._date_range(start, end)
        filters = [Meeting.seller_id.in_(cls._seller_ids_for_agency(agency_id)), Meeting.detected_products.isnot(None)]
        if start_dt:
            filters.append(Meeting.start_time >= start_dt)
        if end_dt:
            filters.append(Meeting.start_time <= end_dt)
        # MVP: group by the text form
        rows = db.session.query(cast(Meeting.detected_products, String).label('product'), func.count(Meeting.id).label('cnt')).filter(and_(*filters)).group_by('product').order_by(func.count(Meeting.id).desc()).limit(limit).all()
        items = [{"product": r.product, "count": int(r.cnt)} for r in rows if r.product]
        summary = ", ".join([f"{i+1}) {it['product']} ({it['count']})" for i, it in enumerate(items)]) or "No data"
        nl = f"Top {limit} products discussed: {summary}."
        return {"answer": nl, "sources": [{"type": "analytics", "metric": "top_products_discussed", "limit": limit, "items": items, "date_range": {"start": start_dt.isoformat() if start_dt else None, "end": end_dt.isoformat() if end_dt else None}}]}

    @classmethod
    def timeseries_calls(cls, *, agency_id: str, start: Optional[datetime], end: Optional[datetime], granularity: str = "daily") -> Dict[str, Any]:
        start_dt, end_dt = cls._date_range(start, end)
        trunc = 'day' if granularity == 'daily' else 'week'
        # answered from meetings
        q_m = db.session.query(func.date_trunc(trunc, Meeting.start_time).label('bucket'), func.count(Meeting.id).label('answered')).filter(Meeting.seller_id.in_(cls._seller_ids_for_agency(agency_id)))
        if start_dt:
            q_m = q_m.filter(Meeting.start_time >= start_dt)
        if end_dt:
            q_m = q_m.filter(Meeting.start_time <= end_dt)
        q_m = q_m.group_by('bucket')

        # unanswered from mobile
        q_c = db.session.query(
            func.date_trunc(trunc, MobileAppCall.start_time).label('bucket'),
            func.count(MobileAppCall.id).label('unanswered')
        ).filter(
            MobileAppCall.user_id.in_(cls._seller_ids_for_agency(agency_id))
        ).filter(
            or_(
                and_(MobileAppCall.call_type == 'incoming', MobileAppCall.status.in_([MobileAppCallStatus.MISSED.value, MobileAppCallStatus.REJECTED.value])),
                and_(MobileAppCall.call_type == 'outgoing', MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
            )
        ).group_by('bucket')
        if start_dt:
            q_c = q_c.filter(MobileAppCall.start_time >= start_dt)
        if end_dt:
            q_c = q_c.filter(MobileAppCall.start_time <= end_dt)

        m = {str(r.bucket): int(r.answered) for r in q_m.all()}
        c = {str(r.bucket): int(r.unanswered) for r in q_c.all()}
        buckets = sorted(set(m.keys()) | set(c.keys()))
        series = [{"bucket": b, "answered": m.get(b, 0), "unanswered": c.get(b, 0), "total": m.get(b, 0) + c.get(b, 0)} for b in buckets]
        # concise NL summary
        total_ans = sum(s['answered'] for s in series)
        total_unans = sum(s['unanswered'] for s in series)
        peak = max(series, key=lambda s: s['total'])['bucket'] if series else None
        nl = f"{granularity.capitalize()} calls from {start_dt.date() if start_dt else 'N/A'} to {end_dt.date() if end_dt else 'N/A'}: answered {total_ans}, unanswered {total_unans}."
        if peak:
            nl += f" Peak on {peak.split(' ')[0]}."
        return {"answer": nl, "sources": [{"type": "analytics", "metric": f"timeseries_calls_{granularity}", "series": series, "date_range": {"start": start_dt.isoformat() if start_dt else None, "end": end_dt.isoformat() if end_dt else None}}]}

    @classmethod
    def count_calls_by_seller_for_product(
        cls,
        *,
        agency_id: str,
        seller_id: str,
        product_query: str,
        start: Optional[datetime],
        end: Optional[datetime],
        max_examples: int = 5,
    ) -> Dict[str, Any]:
        seller = db.session.query(Seller).filter(Seller.id == seller_id, Seller.agency_id == agency_id).first()
        if not seller:
            return {
                "answer": "0",
                "sources": [{"type": "analytics", "reason": "seller_not_in_agency"}],
            }

        from app.models.meeting import Meeting  # local import to avoid circular lint complains
        filters = [Meeting.seller_id == seller_id]
        if start:
            filters.append(Meeting.start_time >= start)
        if end:
            filters.append(Meeting.start_time <= end)
        if product_query:
            filters.append(cast(Meeting.detected_products, String).ilike(f"%{product_query}%"))

        q = db.session.query(Meeting.id).filter(and_(*filters)).order_by(Meeting.start_time.desc())
        ids = [str(r.id) for r in q.limit(max_examples).all()]
        count = q.count()

        return {
            "answer": str(count),
            "sources": [
                {
                    "type": "analytics",
                    "metric": "seller_product_calls",
                    "seller_id": str(seller_id),
                    "product_query": product_query,
                    "example_meetings": ids,
                    "date_range": {
                        "start": start.isoformat() if start else None,
                        "end": end.isoformat() if end else None,
                    },
                }
            ],
        }



