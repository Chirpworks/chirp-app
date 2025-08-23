import os
from typing import List, Tuple

from app import create_app, db
from app.models.meeting import Meeting
from app.models.mobile_app_calls import MobileAppCall
from app.models.seller import Seller
from app.models.buyer import Buyer
from sqlalchemy import and_

AGENCY_ID = os.environ.get("TARGET_AGENCY_ID", "095c46b1-ec69-4df2-bb9d-39cdc2ad17f8")
BATCH_SIZE = int(os.environ.get("CLEANUP_BATCH_SIZE", "1000"))


def fetch_buyers_map() -> dict:
    return {b.id: b.phone for b in Buyer.query}


def fetch_seller_ids_for_agency(agency_id: str) -> List[str]:
    return [s.id for s in Seller.query.filter_by(agency_id=agency_id).all()]


def find_matching_mobile_calls(meeting: Meeting, buyer_phone: str) -> List[MobileAppCall]:
    return (
        MobileAppCall.query
        .filter(
            and_(
                MobileAppCall.user_id == meeting.seller_id,
                MobileAppCall.buyer_number == buyer_phone,
                MobileAppCall.start_time == meeting.start_time,
            )
        )
        .all()
    )


def cleanup():
    app = create_app()
    with app.app_context():
        seller_ids = fetch_seller_ids_for_agency(AGENCY_ID)
        buyers_map = fetch_buyers_map()

        total_meetings = 0
        total_mac_matches = 0
        total_mac_deleted = 0

        offset = 0
        while True:
            meetings_batch: List[Meeting] = (
                db.session.query(Meeting)
                .filter(Meeting.seller_id.in_(seller_ids))
                .order_by(Meeting.start_time.asc())
                .offset(offset)
                .limit(BATCH_SIZE)
                .all()
            )
            if not meetings_batch:
                break

            for m in meetings_batch:
                total_meetings += 1
                buyer_phone = buyers_map.get(m.buyer_id)
                if not buyer_phone:
                    continue
                matches = find_matching_mobile_calls(m, buyer_phone)
                if not matches:
                    continue
                total_mac_matches += len(matches)
                for mac in matches:
                    db.session.delete(mac)
                    total_mac_deleted += 1
            db.session.commit()
            offset += BATCH_SIZE

        print({
            "agency_id": AGENCY_ID,
            "meetings_scanned": total_meetings,
            "mobile_matches_found": total_mac_matches,
            "mobile_calls_deleted": total_mac_deleted,
        })


if __name__ == "__main__":
    cleanup()
