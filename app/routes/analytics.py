import logging
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from app import db, Meeting, MobileAppCall
from app.models.buyer import Buyer
from app.services import SellerService
from app.constants import CallDirection, MobileAppCallStatus
from app.models.seller import SellerRole
from sqlalchemy import func
from app.utils.call_recording_utils import denormalize_phone_number

logging = logging.getLogger(__name__)

analytics_bp = Blueprint("analytics", __name__)


def get_date_range_from_timeframe(time_frame: str):
    kolkata_tz = ZoneInfo("Asia/Kolkata")
    now = datetime.now(kolkata_tz)
    if time_frame == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif time_frame == "this_week":
        days_since_monday = now.weekday()
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
        end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
    elif time_frame == "last_week":
        days_since_monday = now.weekday()
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday + 7)
        end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
    elif time_frame == "this_month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        end_date = next_month - timedelta(microseconds=1)
    elif time_frame == "last_month":
        if now.month == 1:
            start_date = now.replace(year=now.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = now.replace(month=now.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
    else:
        raise ValueError(f"Invalid time_frame: {time_frame}")
    return start_date, end_date

def get_granularity_from_timeframe(time_frame: str) -> str:
    return "hourly" if time_frame == "today" else "daily"


@analytics_bp.route("/total_call_data", methods=["GET"])
@jwt_required()
def get_total_call_data():
    try:
        user_id = get_jwt_identity()
        user = SellerService.get_by_id(user_id)
        if not user:
            return jsonify({"error": "Seller not found"}), 404
        time_frame = request.args.get("time_frame", "today")
        if time_frame not in ["today", "this_week", "last_week", "this_month", "last_month"]:
            return jsonify({"error": "Invalid time_frame. Must be one of: today, this_week, last_week, this_month, last_month"}), 400
        start_date, end_date = get_date_range_from_timeframe(time_frame)
        granularity = get_granularity_from_timeframe(time_frame)
        agency_sellers = SellerService.get_by_agency(user.agency_id)
        if granularity == "hourly":
            sales_data = {}
            total_outgoing_calls = 0
            total_incoming_calls = 0
            total_unique_leads = 0
            for hour in range(24):
                hour_start = start_date.replace(hour=hour)
                hour_end = hour_start.replace(minute=59, second=59, microsecond=999999)
                
                # Count outgoing calls that resulted in meetings (answered)
                outgoing_calls_answered_in_hour = (
                    Meeting.query
                    .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                    .filter(Meeting.direction == CallDirection.OUTGOING.value)
                    .filter(Meeting.start_time >= hour_start)
                    .filter(Meeting.start_time <= hour_end)
                    .count()
                )
                
                # Count incoming calls that resulted in meetings (answered)
                incoming_calls_answered_in_hour = (
                    Meeting.query
                    .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                    .filter(Meeting.direction == CallDirection.INCOMING.value)
                    .filter(Meeting.start_time >= hour_start)
                    .filter(Meeting.start_time <= hour_end)
                    .count()
                )
                
                # Count unanswered outgoing calls from MobileAppCall table
                outgoing_calls_unanswered_in_hour = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.call_type == "outgoing")
                    .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                    .filter(MobileAppCall.start_time >= hour_start)
                    .filter(MobileAppCall.start_time <= hour_end)
                    .count()
                )
                
                # Count incoming unanswered calls (missed and rejected) from MobileAppCall table
                incoming_calls_unanswered_in_hour = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.call_type == "incoming")
                    .filter(MobileAppCall.status.in_([
                        MobileAppCallStatus.MISSED.value,
                        MobileAppCallStatus.REJECTED.value
                    ]))
                    .filter(MobileAppCall.start_time >= hour_start)
                    .filter(MobileAppCall.start_time <= hour_end)
                    .count()
                )
                
                # Total calls by direction
                outgoing_calls_in_hour = outgoing_calls_answered_in_hour + outgoing_calls_unanswered_in_hour
                incoming_calls_in_hour = incoming_calls_answered_in_hour + incoming_calls_unanswered_in_hour
                
                # Get unique buyer phone numbers from both Meeting and MobileAppCall tables
                # Query 1: Get buyer phone numbers from Meeting table (via buyer relationship)
                meeting_buyer_phones_hour = (
                    db.session.query(Buyer.phone.label('phone'))
                    .join(Meeting, Meeting.buyer_id == Buyer.id)
                    .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                    .filter(Meeting.start_time >= hour_start)
                    .filter(Meeting.start_time <= hour_end)
                )
                
                # Query 2: Get buyer phone numbers from unanswered outgoing calls
                # These represent buyers that sellers tried to engage but didn't connect
                unanswered_outgoing_buyer_phones_hour = (
                    db.session.query(MobileAppCall.buyer_number.label('phone'))
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.call_type == "outgoing")
                    .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                    .filter(MobileAppCall.start_time >= hour_start)
                    .filter(MobileAppCall.start_time <= hour_end)
                )
                
                # Use UNION to combine both sets and count unique buyer phone numbers
                # Only include actual conversations (meetings) and outbound contact attempts
                combined_query_hour = meeting_buyer_phones_hour.union(unanswered_outgoing_buyer_phones_hour)
                unique_leads_in_hour = (
                    db.session.query(func.count(func.distinct(combined_query_hour.subquery().c.phone)))
                    .scalar() or 0
                )
                sales_data[f"hour{hour}"] = {
                    "outgoing_calls": outgoing_calls_in_hour,
                    "incoming_calls": incoming_calls_in_hour,
                    "unique_leads_engaged": unique_leads_in_hour
                }
                total_outgoing_calls += outgoing_calls_in_hour
                total_incoming_calls += incoming_calls_in_hour
                total_unique_leads += unique_leads_in_hour
        else:
            sales_data = {}
            total_outgoing_calls = 0
            total_incoming_calls = 0
            total_unique_leads = 0
            current_date = start_date
            day_count = 0
            while current_date <= end_date:
                day_start = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = current_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                # Count outgoing calls that resulted in meetings (answered)
                outgoing_calls_answered_in_day = (
                    Meeting.query
                    .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                    .filter(Meeting.direction == CallDirection.OUTGOING.value)
                    .filter(Meeting.start_time >= day_start)
                    .filter(Meeting.start_time <= day_end)
                    .count()
                )
                
                # Count incoming calls that resulted in meetings (answered)
                incoming_calls_answered_in_day = (
                    Meeting.query
                    .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                    .filter(Meeting.direction == CallDirection.INCOMING.value)
                    .filter(Meeting.start_time >= day_start)
                    .filter(Meeting.start_time <= day_end)
                    .count()
                )
                
                # Count unanswered outgoing calls from MobileAppCall table
                outgoing_calls_unanswered_in_day = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.call_type == "outgoing")
                    .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                    .filter(MobileAppCall.start_time >= day_start)
                    .filter(MobileAppCall.start_time <= day_end)
                    .count()
                )
                
                # Count incoming unanswered calls (missed and rejected) from MobileAppCall table
                incoming_calls_unanswered_in_day = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.call_type == "incoming")
                    .filter(MobileAppCall.status.in_([
                        MobileAppCallStatus.MISSED.value,
                        MobileAppCallStatus.REJECTED.value
                    ]))
                    .filter(MobileAppCall.start_time >= day_start)
                    .filter(MobileAppCall.start_time <= day_end)
                    .count()
                )
                
                # Total calls by direction
                outgoing_calls_in_day = outgoing_calls_answered_in_day + outgoing_calls_unanswered_in_day
                incoming_calls_in_day = incoming_calls_answered_in_day + incoming_calls_unanswered_in_day
                
                # Get unique buyer phone numbers from both Meeting and MobileAppCall tables
                # Query 1: Get buyer phone numbers from Meeting table (via buyer relationship)
                meeting_buyer_phones_day = (
                    db.session.query(Buyer.phone.label('phone'))
                    .join(Meeting, Meeting.buyer_id == Buyer.id)
                    .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                    .filter(Meeting.start_time >= day_start)
                    .filter(Meeting.start_time <= day_end)
                )
                
                # Query 2: Get buyer phone numbers from unanswered outgoing calls
                # These represent buyers that sellers tried to engage but didn't connect
                unanswered_outgoing_buyer_phones_day = (
                    db.session.query(MobileAppCall.buyer_number.label('phone'))
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.call_type == "outgoing")
                    .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                    .filter(MobileAppCall.start_time >= day_start)
                    .filter(MobileAppCall.start_time <= day_end)
                )
                
                # Use UNION to combine both sets and count unique buyer phone numbers
                # Only include actual conversations (meetings) and outbound contact attempts
                combined_query_day = meeting_buyer_phones_day.union(unanswered_outgoing_buyer_phones_day)
                unique_leads_in_day = (
                    db.session.query(func.count(func.distinct(combined_query_day.subquery().c.phone)))
                    .scalar() or 0
                )
                sales_data[f"day{day_count}"] = {
                    "outgoing_calls": outgoing_calls_in_day,
                    "incoming_calls": incoming_calls_in_day,
                    "unique_leads_engaged": unique_leads_in_day
                }
                total_outgoing_calls += outgoing_calls_in_day
                total_incoming_calls += incoming_calls_in_day
                total_unique_leads += unique_leads_in_day
                current_date += timedelta(days=1)
                day_count += 1
        result = {
            "sales_data": sales_data,
            "total_data": {
                "total_outgoing_calls": total_outgoing_calls,
                "total_incoming_calls": total_incoming_calls,
                "total_calls": total_outgoing_calls + total_incoming_calls,
                "unique_leads_engaged": total_unique_leads
            }
        }
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Failed to fetch total call data: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch total call data: {str(e)}"}), 500


@analytics_bp.route("/team_call_data", methods=["GET"])
@jwt_required()
def get_team_call_data():
    try:
        user_id = get_jwt_identity()
        user = SellerService.get_by_id(user_id)
        if not user:
            return jsonify({"error": "Seller not found"}), 404
        time_frame = request.args.get("time_frame", "today")
        if time_frame not in ["today", "this_week", "last_week", "this_month", "last_month"]:
            return jsonify({"error": "Invalid time_frame. Must be one of: today, this_week, last_week, this_month, last_month"}), 400
        start_date, end_date = get_date_range_from_timeframe(time_frame)
        agency_sellers = SellerService.get_by_agency(user.agency_id)
        seller_data = []
        for seller in agency_sellers:
            # Count outgoing calls that resulted in meetings (answered)
            outgoing_calls_answered = (
                Meeting.query
                .filter(Meeting.seller_id == seller.id)
                .filter(Meeting.direction == CallDirection.OUTGOING.value)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .count()
            )
            
            # Count incoming calls that resulted in meetings (answered)
            incoming_calls_answered = (
                Meeting.query
                .filter(Meeting.seller_id == seller.id)
                .filter(Meeting.direction == CallDirection.INCOMING.value)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .count()
            )
            
            # Count unanswered outgoing calls from MobileAppCall table
            outgoing_calls_unanswered = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id == seller.id)
                .filter(MobileAppCall.call_type == "outgoing")
                .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
                .count()
            )
            
            # Count incoming unanswered calls (missed and rejected) from MobileAppCall table
            incoming_calls_unanswered = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id == seller.id)
                .filter(MobileAppCall.call_type == "incoming")
                .filter(MobileAppCall.status.in_([
                    MobileAppCallStatus.MISSED.value,
                    MobileAppCallStatus.REJECTED.value
                ]))
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
                .count()
            )
            
            # Total calls by direction
            outgoing_calls = outgoing_calls_answered + outgoing_calls_unanswered
            incoming_calls = incoming_calls_answered + incoming_calls_unanswered
            total_calls = outgoing_calls + incoming_calls
            
            # Get unique buyer phone numbers from both Meeting and MobileAppCall tables
            # to avoid double-counting the same buyer
            
            # Query 1: Get buyer phone numbers from Meeting table (via buyer relationship)
            meeting_buyer_phones = (
                db.session.query(Buyer.phone.label('phone'))
                .join(Meeting, Meeting.buyer_id == Buyer.id)
                .filter(Meeting.seller_id == seller.id)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
            )
            
            # Query 2: Get buyer phone numbers from unanswered outgoing calls
            # These represent buyers that sellers tried to engage but didn't connect
            unanswered_outgoing_buyer_phones = (
                db.session.query(MobileAppCall.buyer_number.label('phone'))
                .filter(MobileAppCall.user_id == seller.id)
                .filter(MobileAppCall.call_type == "outgoing")
                .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
            )
            
            # Use UNION to combine both sets and count unique buyer phone numbers
            # Only include actual conversations (meetings) and outbound contact attempts
            combined_query = meeting_buyer_phones.union(unanswered_outgoing_buyer_phones)
            unique_leads = (
                db.session.query(func.count(func.distinct(combined_query.subquery().c.phone)))
                .scalar() or 0
            )
            seller_data.append({
                "seller_id": str(seller.id),
                "seller_name": seller.name,
                "seller_phone": denormalize_phone_number(seller.phone),
                "metrics": {
                    "total_calls_made": total_calls,
                    "outgoing_calls": outgoing_calls,
                    "incoming_calls": incoming_calls,
                    "leads_engaged": unique_leads
                }
            })
        result = {"seller_data": seller_data}
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Failed to fetch team call data: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch team call data: {str(e)}"}), 500


@analytics_bp.route("/call_data/<uuid:seller_uuid>", methods=["GET"])
@jwt_required()
def get_call_data(seller_uuid):
    try:
        user_id = get_jwt_identity()
        user = SellerService.get_by_id(user_id)
        if not user:
            return jsonify({"error": "Seller not found"}), 404
        time_frame = request.args.get("time_frame", "today")
        if time_frame not in ["today", "this_week", "last_week", "this_month", "last_month"]:
            return jsonify({"error": "Invalid time_frame. Must be one of: today, this_week, last_week, this_month, last_month"}), 400
        start_date, end_date = get_date_range_from_timeframe(time_frame)
        seller = SellerService.get_by_id(str(seller_uuid))
        if not seller:
            return jsonify({"error": "Seller not found"}), 404
        if seller.agency_id != user.agency_id:
            return jsonify({"error": "Unauthorized access to seller data"}), 403
        # Count outgoing calls that resulted in meetings (answered)
        outgoing_calls_answered = (
            Meeting.query
            .filter(Meeting.seller_id == seller_uuid)
            .filter(Meeting.direction == CallDirection.OUTGOING.value)
            .filter(Meeting.start_time >= start_date)
            .filter(Meeting.start_time <= end_date)
            .count()
        )
        
        # Count incoming calls that resulted in meetings (answered)
        incoming_calls_answered = (
            Meeting.query
            .filter(Meeting.seller_id == seller_uuid)
            .filter(Meeting.direction == CallDirection.INCOMING.value)
            .filter(Meeting.start_time >= start_date)
            .filter(Meeting.start_time <= end_date)
            .count()
        )
        
        # Count unanswered outgoing calls from MobileAppCall table
        outgoing_calls_unanswered = (
            MobileAppCall.query
            .filter(MobileAppCall.user_id == seller_uuid)
            .filter(MobileAppCall.call_type == "outgoing")
            .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
            .filter(MobileAppCall.start_time >= start_date)
            .filter(MobileAppCall.start_time <= end_date)
            .count()
        )
        
        # Total outgoing calls = answered + unanswered
        outgoing_calls = outgoing_calls_answered + outgoing_calls_unanswered
        
        # Count incoming unanswered calls (missed and rejected) from MobileAppCall table
        incoming_calls_unanswered = (
            MobileAppCall.query
            .filter(MobileAppCall.user_id == seller_uuid)
            .filter(MobileAppCall.call_type == "incoming")
            .filter(MobileAppCall.status.in_([
                MobileAppCallStatus.MISSED.value,
                MobileAppCallStatus.REJECTED.value
            ]))
            .filter(MobileAppCall.start_time >= start_date)
            .filter(MobileAppCall.start_time <= end_date)
            .count()
        )
        
        # Total incoming calls = answered + unanswered
        incoming_calls = incoming_calls_answered + incoming_calls_unanswered
        
        # Calculate unique leads engaged using UNION query to avoid double-counting
        # Query 1: Get buyer phone numbers from Meeting table (via buyer relationship)
        meeting_buyer_phones = (
            db.session.query(Buyer.phone.label('phone'))
            .join(Meeting, Meeting.buyer_id == Buyer.id)
            .filter(Meeting.seller_id == seller_uuid)
            .filter(Meeting.start_time >= start_date)
            .filter(Meeting.start_time <= end_date)
        )
        
        # Query 2: Get buyer phone numbers from unanswered outgoing calls
        unanswered_outgoing_buyer_phones = (
            db.session.query(MobileAppCall.buyer_number.label('phone'))
            .filter(MobileAppCall.user_id == seller_uuid)
            .filter(MobileAppCall.call_type == "outgoing")
            .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
            .filter(MobileAppCall.start_time >= start_date)
            .filter(MobileAppCall.start_time <= end_date)
        )
        
        # Use UNION to combine both sets and count unique buyer phone numbers
        # Only include actual conversations (meetings) and outbound contact attempts
        combined_query = meeting_buyer_phones.union(unanswered_outgoing_buyer_phones)
        unique_leads_engaged = (
            db.session.query(func.count(func.distinct(combined_query.subquery().c.phone)))
            .scalar() or 0
        )
        
        result = {
            "outgoing_calls": outgoing_calls,
            "outgoing_calls_answered": outgoing_calls_answered,
            "outgoing_calls_unanswered": outgoing_calls_unanswered,
            "incoming_calls": incoming_calls,
            "incoming_calls_answered": incoming_calls_answered,
            "incoming_calls_unanswered": incoming_calls_unanswered,
            "total_calls": outgoing_calls + incoming_calls,
            "unique_leads_engaged": unique_leads_engaged
        }
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Failed to fetch call data for seller {seller_uuid}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch call data: {str(e)}"}), 500


@analytics_bp.route("/seller_call_analytics", methods=["GET"])
@jwt_required()
def get_seller_call_analytics():
    try:
        user_id = get_jwt_identity()
        user = SellerService.get_by_id(user_id)
        if not user:
            return jsonify({"error": "Seller not found"}), 404
        time_frame = request.args.get("time_frame", "today")
        if time_frame not in ["today", "this_week", "last_week", "this_month", "last_month"]:
            return jsonify({"error": "Invalid time_frame. Must be one of: today, this_week, last_week, this_month, last_month"}), 400
        team_member_ids = request.args.getlist("team_member_ids")
        if not team_member_ids:
            return jsonify({"error": "team_member_ids parameter is required"}), 400
        start_date, end_date = get_date_range_from_timeframe(time_frame)
        seller_data = []
        for seller_id in team_member_ids:
            seller = SellerService.get_by_id(seller_id)
            if not seller:
                continue
            if seller.agency_id != user.agency_id:
                continue
            
            # Count outgoing calls that resulted in meetings (answered)
            outgoing_calls_answered = (
                Meeting.query
                .filter(Meeting.seller_id == seller_id)
                .filter(Meeting.direction == CallDirection.OUTGOING.value)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .count()
            )
            
            # Count incoming calls that resulted in meetings (answered)
            incoming_calls_answered = (
                Meeting.query
                .filter(Meeting.seller_id == seller_id)
                .filter(Meeting.direction == CallDirection.INCOMING.value)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .count()
            )
            
            # Count unanswered outgoing calls from MobileAppCall table
            unanswered_outgoing_calls = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id == seller_id)
                .filter(MobileAppCall.call_type == "outgoing")
                .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
                .count()
            )
            
            # Count incoming unanswered calls (missed and rejected) from MobileAppCall table
            incoming_calls_unanswered = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id == seller_id)
                .filter(MobileAppCall.call_type == "incoming")
                .filter(MobileAppCall.status.in_([
                    MobileAppCallStatus.MISSED.value,
                    MobileAppCallStatus.REJECTED.value
                ]))
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
                .count()
            )
            
            # Total calls = answered + unanswered for each direction
            outgoing_calls = outgoing_calls_answered + unanswered_outgoing_calls
            incoming_calls = incoming_calls_answered + incoming_calls_unanswered
            
            # Calculate unique leads engaged using UNION query to avoid double-counting
            # Query 1: Get buyer phone numbers from Meeting table (via buyer relationship)
            meeting_buyer_phones = (
                db.session.query(Buyer.phone.label('phone'))
                .join(Meeting, Meeting.buyer_id == Buyer.id)
                .filter(Meeting.seller_id == seller_id)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
            )
            
            # Query 2: Get buyer phone numbers from unanswered outgoing calls
            # These represent buyers that sellers tried to engage but didn't connect
            unanswered_outgoing_buyer_phones = (
                db.session.query(MobileAppCall.buyer_number.label('phone'))
                .filter(MobileAppCall.user_id == seller_id)
                .filter(MobileAppCall.call_type == "outgoing")
                .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
            )
            
            # Use UNION to combine both sets and count unique buyer phone numbers
            # Only include actual conversations (meetings) and outbound contact attempts
            combined_query = meeting_buyer_phones.union(unanswered_outgoing_buyer_phones)
            unique_leads_engaged = (
                db.session.query(func.count(func.distinct(combined_query.subquery().c.phone)))
                .scalar() or 0
            )
            
            seller_data.append({
                "seller_id": seller_id,
                "seller_name": seller.name,
                "seller_phone": seller.phone,
                "seller_email": seller.email,
                "outgoing_calls": outgoing_calls,
                "outgoing_calls_answered": outgoing_calls_answered,
                "outgoing_calls_unanswered": unanswered_outgoing_calls,
                "incoming_calls": incoming_calls,
                "incoming_calls_answered": incoming_calls_answered,
                "incoming_calls_unanswered": incoming_calls_unanswered,
                "total_calls": outgoing_calls + incoming_calls,
                "unique_leads_engaged": unique_leads_engaged
            })
        result = {"seller_data": seller_data}
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Failed to fetch seller call analytics: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch seller call analytics: {str(e)}"}), 500
