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
from app.utils.time_utils import get_date_range_from_timeframe, get_granularity_from_timeframe, validate_time_frame, parse_date_range_params

logging = logging.getLogger(__name__)

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/total_call_data", methods=["GET"])
@jwt_required()
def get_total_call_data():
    try:
        user_id = get_jwt_identity()
        user = SellerService.get_by_id(user_id)
        if not user:
            return jsonify({"error": "Seller not found"}), 404
        
        # Parse date range parameters (supports both new date range and legacy time_frame)
        start_date, end_date, error_response = parse_date_range_params(default_days_back=7, max_days_range=90)
        if error_response:
            return jsonify(error_response[0]), error_response[1]
        
        # Determine granularity
        date_diff = (end_date - start_date).days
        granularity = "hourly" if date_diff <= 2 else "daily"
        agency_sellers = SellerService.get_by_agency(user.agency_id)
        agency_sellers = [seller for seller in agency_sellers if seller.role != SellerRole.MANAGER]
        
        if granularity == "hourly":
            sales_data = {}
            total_outgoing_calls = 0
            total_incoming_calls = 0
            total_unique_leads = 0
            for hour in range(24):
                hour_start = start_date.replace(hour=hour)
                hour_end = hour_start.replace(minute=59, second=59, microsecond=999999)
                
                # Meetings answered
                outgoing_meet = (
                    Meeting.query
                    .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                    .filter(Meeting.direction == CallDirection.OUTGOING.value)
                    .filter(Meeting.start_time >= hour_start)
                    .filter(Meeting.start_time <= hour_end)
                    .count()
                )
                incoming_meet = (
                    Meeting.query
                    .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                    .filter(Meeting.direction == CallDirection.INCOMING.value)
                    .filter(Meeting.start_time >= hour_start)
                    .filter(Meeting.start_time <= hour_end)
                    .count()
                )
                # Mobile processing treated as answered
                outgoing_proc = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.call_type == "outgoing")
                    .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                    .filter(MobileAppCall.start_time >= hour_start)
                    .filter(MobileAppCall.start_time <= hour_end)
                    .count()
                )
                incoming_proc = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.call_type == "incoming")
                    .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                    .filter(MobileAppCall.start_time >= hour_start)
                    .filter(MobileAppCall.start_time <= hour_end)
                    .count()
                )
                # Unanswered
                outgoing_unans = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.call_type == "outgoing")
                    .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                    .filter(MobileAppCall.start_time >= hour_start)
                    .filter(MobileAppCall.start_time <= hour_end)
                    .count()
                )
                incoming_unans = (
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
                outgoing_calls_in_hour = outgoing_meet + outgoing_proc + outgoing_unans
                incoming_calls_in_hour = incoming_meet + incoming_proc + incoming_unans
                
                # Unique leads engaged = distinct buyer phones from Meetings (answered)
                # UNION distinct buyer_number from MobileAppCall with Processing status (answered not yet reconciled)
                meeting_phones_q = (
                    db.session.query(Buyer.phone.label('phone'))
                    .join(Meeting, Meeting.buyer_id == Buyer.id)
                    .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                    .filter(Meeting.start_time >= hour_start)
                    .filter(Meeting.start_time <= hour_end)
                    .distinct()
                )
                mac_phones_q = (
                    db.session.query(MobileAppCall.buyer_number.label('phone'))
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                    .filter(MobileAppCall.start_time >= hour_start)
                    .filter(MobileAppCall.start_time <= hour_end)
                    .distinct()
                )
                union_phones_hour = meeting_phones_q.union(mac_phones_q).subquery()
                unique_leads_in_hour = db.session.query(func.count()).select_from(union_phones_hour).scalar() or 0
                sales_data[f"hour{hour}"] = {
                    "outgoing_calls": outgoing_calls_in_hour,
                    "incoming_calls": incoming_calls_in_hour,
                    "unique_leads_engaged": unique_leads_in_hour
                }
                total_outgoing_calls += outgoing_calls_in_hour
                total_incoming_calls += incoming_calls_in_hour
                total_unique_leads += unique_leads_in_hour
            meeting_phones_total_q = (
                db.session.query(Buyer.phone.label('phone'))
                .join(Meeting, Meeting.buyer_id == Buyer.id)
                .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .distinct()
            )
            mac_phones_total_q = (
                db.session.query(MobileAppCall.buyer_number.label('phone'))
                .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
                .distinct()
            )
            union_phones_total = meeting_phones_total_q.union(mac_phones_total_q).subquery()
            total_unique_leads_corrected = db.session.query(func.count()).select_from(union_phones_total).scalar() or 0
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
                outgoing_meet = (
                    Meeting.query
                    .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                    .filter(Meeting.direction == CallDirection.OUTGOING.value)
                    .filter(Meeting.start_time >= day_start)
                    .filter(Meeting.start_time <= day_end)
                    .count()
                )
                incoming_meet = (
                    Meeting.query
                    .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                    .filter(Meeting.direction == CallDirection.INCOMING.value)
                    .filter(Meeting.start_time >= day_start)
                    .filter(Meeting.start_time <= day_end)
                    .count()
                )
                outgoing_proc = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.call_type == "outgoing")
                    .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                    .filter(MobileAppCall.start_time >= day_start)
                    .filter(MobileAppCall.start_time <= day_end)
                    .count()
                )
                incoming_proc = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.call_type == "incoming")
                    .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                    .filter(MobileAppCall.start_time >= day_start)
                    .filter(MobileAppCall.start_time <= day_end)
                    .count()
                )
                outgoing_unans = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.call_type == "outgoing")
                    .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                    .filter(MobileAppCall.start_time >= day_start)
                    .filter(MobileAppCall.start_time <= day_end)
                    .count()
                )
                incoming_unans = (
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
                outgoing_calls_in_day = outgoing_meet + outgoing_proc + outgoing_unans
                incoming_calls_in_day = incoming_meet + incoming_proc + incoming_unans
                meeting_phones_day_q = (
                    db.session.query(Buyer.phone.label('phone'))
                    .join(Meeting, Meeting.buyer_id == Buyer.id)
                    .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                    .filter(Meeting.start_time >= day_start)
                    .filter(Meeting.start_time <= day_end)
                    .distinct()
                )
                mac_phones_day_q = (
                    db.session.query(MobileAppCall.buyer_number.label('phone'))
                    .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                    .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                    .filter(MobileAppCall.start_time >= day_start)
                    .filter(MobileAppCall.start_time <= day_end)
                    .distinct()
                )
                union_phones_day = meeting_phones_day_q.union(mac_phones_day_q).subquery()
                unique_leads_in_day = db.session.query(func.count()).select_from(union_phones_day).scalar() or 0
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
            meeting_phones_total_q = (
                db.session.query(Buyer.phone.label('phone'))
                .join(Meeting, Meeting.buyer_id == Buyer.id)
                .filter(Meeting.seller_id.in_([s.id for s in agency_sellers]))
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .distinct()
            )
            mac_phones_total_q = (
                db.session.query(MobileAppCall.buyer_number.label('phone'))
                .filter(MobileAppCall.user_id.in_([s.id for s in agency_sellers]))
                .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
                .distinct()
            )
            union_phones_total = meeting_phones_total_q.union(mac_phones_total_q).subquery()
            total_unique_leads_corrected = db.session.query(func.count()).select_from(union_phones_total).scalar() or 0
        result = {
            "sales_data": sales_data,
            "total_data": {
                "total_outgoing_calls": total_outgoing_calls,
                "total_incoming_calls": total_incoming_calls,
                "total_calls": total_outgoing_calls + total_incoming_calls,
                "unique_leads_engaged": total_unique_leads_corrected
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
        
        # Parse date range parameters (supports both new date range and legacy time_frame)
        start_date, end_date, error_response = parse_date_range_params(default_days_back=7, max_days_range=90)
        if error_response:
            return jsonify(error_response[0]), error_response[1]
        agency_sellers = SellerService.get_by_agency(user.agency_id)
        # Filter out managers for average calculations
        agency_sellers = [seller for seller in agency_sellers if seller.role != SellerRole.MANAGER]
        seller_data = []
        for seller in agency_sellers:
            # Count outgoing calls that resulted in meetings (answered)
            outgoing_calls_answered_meetings = (
                Meeting.query
                .filter(Meeting.seller_id == seller.id)
                .filter(Meeting.direction == CallDirection.OUTGOING.value)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .count()
            )
            # Include MobileAppCall Processing as answered (outgoing)
            outgoing_calls_answered_processing = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id == seller.id)
                .filter(MobileAppCall.call_type == "outgoing")
                .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
                .count()
            )
            outgoing_calls_answered = outgoing_calls_answered_meetings + outgoing_calls_answered_processing
            
            # Count incoming calls that resulted in meetings (answered)
            incoming_calls_answered_meetings = (
                Meeting.query
                .filter(Meeting.seller_id == seller.id)
                .filter(Meeting.direction == CallDirection.INCOMING.value)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .count()
            )
            # Include MobileAppCall Processing as answered (incoming)
            incoming_calls_answered_processing = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id == seller.id)
                .filter(MobileAppCall.call_type == "incoming")
                .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
                .count()
            )
            incoming_calls_answered = incoming_calls_answered_meetings + incoming_calls_answered_processing
            
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
            
            # Total calls by direction (answered + unanswered)
            outgoing_calls = outgoing_calls_answered + outgoing_calls_unanswered
            incoming_calls = incoming_calls_answered + incoming_calls_unanswered
            total_calls = outgoing_calls + incoming_calls
            
            # Unique leads engaged per seller = distinct buyer phones from Meetings
            # UNION distinct MobileAppCall.buyer_number with Processing
            meeting_phones_q = (
                db.session.query(Buyer.phone.label('phone'))
                .join(Meeting, Meeting.buyer_id == Buyer.id)
                .filter(Meeting.seller_id == seller.id)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .distinct()
            )
            mac_phones_q = (
                db.session.query(MobileAppCall.buyer_number.label('phone'))
                .filter(MobileAppCall.user_id == seller.id)
                .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
                .distinct()
            )
            union_phones = meeting_phones_q.union(mac_phones_q).subquery()
            unique_leads = db.session.query(func.count()).select_from(union_phones).scalar() or 0
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
        
        # Parse date range parameters (supports both new date range and legacy time_frame)
        start_date, end_date, error_response = parse_date_range_params(default_days_back=7, max_days_range=90)
        if error_response:
            return jsonify(error_response[0]), error_response[1]
        seller = SellerService.get_by_id(str(seller_uuid))
        if not seller:
            return jsonify({"error": "Seller not found"}), 404
        if seller.agency_id != user.agency_id:
            return jsonify({"error": "Unauthorized access to seller data"}), 403
        
        outgoing_meet = (
            Meeting.query
            .filter(Meeting.seller_id == seller_uuid)
            .filter(Meeting.direction == CallDirection.OUTGOING.value)
            .filter(Meeting.start_time >= start_date)
            .filter(Meeting.start_time <= end_date)
            .count()
        )
        incoming_meet = (
            Meeting.query
            .filter(Meeting.seller_id == seller_uuid)
            .filter(Meeting.direction == CallDirection.INCOMING.value)
            .filter(Meeting.start_time >= start_date)
            .filter(Meeting.start_time <= end_date)
            .count()
        )
        outgoing_proc = (
            MobileAppCall.query
            .filter(MobileAppCall.user_id == seller_uuid)
            .filter(MobileAppCall.call_type == "outgoing")
            .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
            .filter(MobileAppCall.start_time >= start_date)
            .filter(MobileAppCall.start_time <= end_date)
            .count()
        )
        incoming_proc = (
            MobileAppCall.query
            .filter(MobileAppCall.user_id == seller_uuid)
            .filter(MobileAppCall.call_type == "incoming")
            .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
            .filter(MobileAppCall.start_time >= start_date)
            .filter(MobileAppCall.start_time <= end_date)
            .count()
        )
        
        outgoing_calls_unanswered = (
            MobileAppCall.query
            .filter(MobileAppCall.user_id == seller_uuid)
            .filter(MobileAppCall.call_type == "outgoing")
            .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
            .filter(MobileAppCall.start_time >= start_date)
            .filter(MobileAppCall.start_time <= end_date)
            .count()
        )
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
        
        outgoing_calls = outgoing_meet + outgoing_proc + outgoing_calls_unanswered
        incoming_calls = incoming_meet + incoming_proc + incoming_calls_unanswered
        
        result = {
            "outgoing_calls": outgoing_calls,
            "outgoing_calls_answered": outgoing_meet + outgoing_proc,
            "outgoing_calls_unanswered": outgoing_calls_unanswered,
            "incoming_calls": incoming_calls,
            "incoming_calls_answered": incoming_meet + incoming_proc,
            "incoming_calls_unanswered": incoming_calls_unanswered,
            "total_calls": outgoing_calls + incoming_calls,
            "unique_leads_engaged": (
                db.session.query(func.count(func.distinct(Buyer.phone)))
                .join(Meeting, Meeting.buyer_id == Buyer.id)
                .filter(Meeting.seller_id == seller_uuid)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .scalar() or 0
            )
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
        
        start_date, end_date, error_response = parse_date_range_params(default_days_back=7, max_days_range=90)
        if error_response:
            return jsonify(error_response[0]), error_response[1]
        
        team_member_ids = request.args.getlist("team_member_ids")
        if not team_member_ids:
            return jsonify({"error": "team_member_ids parameter is required"}), 400
        seller_data = []
        for seller_id in team_member_ids:
            seller = SellerService.get_by_id(seller_id)
            if not seller or seller.agency_id != user.agency_id or seller.role == SellerRole.MANAGER:
                continue
            outgoing_meet = (
                Meeting.query
                .filter(Meeting.seller_id == seller_id)
                .filter(Meeting.direction == CallDirection.OUTGOING.value)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .count()
            )
            incoming_meet = (
                Meeting.query
                .filter(Meeting.seller_id == seller_id)
                .filter(Meeting.direction == CallDirection.INCOMING.value)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .count()
            )
            outgoing_proc = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id == seller_id)
                .filter(MobileAppCall.call_type == "outgoing")
                .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
                .count()
            )
            incoming_proc = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id == seller_id)
                .filter(MobileAppCall.call_type == "incoming")
                .filter(MobileAppCall.status == MobileAppCallStatus.PROCESSING.value)
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
                .count()
            )
            unanswered_outgoing_calls = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id == seller_id)
                .filter(MobileAppCall.call_type == "outgoing")
                .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                .filter(MobileAppCall.start_time >= start_date)
                .filter(MobileAppCall.start_time <= end_date)
                .count()
            )
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
            outgoing_calls = outgoing_meet + outgoing_proc + unanswered_outgoing_calls
            incoming_calls = incoming_meet + incoming_proc + incoming_calls_unanswered
            seller_data.append({
                "seller_id": seller_id,
                "seller_name": seller.name,
                "seller_phone": seller.phone,
                "seller_email": seller.email,
                "outgoing_calls": outgoing_calls,
                "outgoing_calls_answered": outgoing_meet + outgoing_proc,
                "outgoing_calls_unanswered": unanswered_outgoing_calls,
                "incoming_calls": incoming_calls,
                "incoming_calls_answered": incoming_meet + incoming_proc,
                "incoming_calls_unanswered": incoming_calls_unanswered,
                "total_calls": outgoing_calls + incoming_calls,
                "unique_leads_engaged": (
                    db.session.query(func.count(func.distinct(Buyer.phone)))
                    .join(Meeting, Meeting.buyer_id == Buyer.id)
                    .filter(Meeting.seller_id == seller_id)
                    .filter(Meeting.start_time >= start_date)
                    .filter(Meeting.start_time <= end_date)
                    .scalar() or 0
                )
            })
        result = {"seller_data": seller_data}
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Failed to fetch seller call analytics: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch seller call analytics: {str(e)}"}), 500


@analytics_bp.route("/seller_call_data/<uuid:seller_uuid>", methods=["GET"])
@jwt_required()
def get_seller_call_data(seller_uuid):
    """
    Get time-wise breakdown of call analytics data for a specific seller.
    Similar to total_call_data but scoped to individual seller.
    """
    try:
        user_id = get_jwt_identity()
        user = SellerService.get_by_id(user_id)
        if not user:
            return jsonify({"error": "Seller not found"}), 404
        
        # Get and validate the target seller
        seller = SellerService.get_by_id(str(seller_uuid))
        if not seller:
            return jsonify({"error": "Target seller not found"}), 404
        
        # Check if user has access to this seller's data (same agency)
        if seller.agency_id != user.agency_id:
            return jsonify({"error": "Unauthorized access to seller data"}), 403
        
        # Parse date range parameters (supports both new date range and legacy time_frame)
        start_date, end_date, error_response = parse_date_range_params(default_days_back=7, max_days_range=90)
        if error_response:
            return jsonify(error_response[0]), error_response[1]
        
        # Determine granularity based on date range (for backward compatibility)
        date_diff = (end_date - start_date).days
        if date_diff <= 2:
            granularity = "hourly"
        else:
            granularity = "daily"
        
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
                    .filter(Meeting.seller_id == seller_uuid)
                    .filter(Meeting.direction == CallDirection.OUTGOING.value)
                    .filter(Meeting.start_time >= hour_start)
                    .filter(Meeting.start_time <= hour_end)
                    .count()
                )
                
                # Count incoming calls that resulted in meetings (answered)
                incoming_calls_answered_in_hour = (
                    Meeting.query
                    .filter(Meeting.seller_id == seller_uuid)
                    .filter(Meeting.direction == CallDirection.INCOMING.value)
                    .filter(Meeting.start_time >= hour_start)
                    .filter(Meeting.start_time <= hour_end)
                    .count()
                )
                
                # Count unanswered outgoing calls from MobileAppCall table
                outgoing_calls_unanswered_in_hour = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id == seller_uuid)
                    .filter(MobileAppCall.call_type == "outgoing")
                    .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                    .filter(MobileAppCall.start_time >= hour_start)
                    .filter(MobileAppCall.start_time <= hour_end)
                    .count()
                )
                
                # Count incoming unanswered calls (missed and rejected) from MobileAppCall table
                incoming_calls_unanswered_in_hour = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id == seller_uuid)
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
                
                # Get unique buyer phone numbers only from Meeting table (actual conversations)
                # Only count buyers who had actual meetings/conversations
                unique_leads_in_hour = (
                    db.session.query(func.count(func.distinct(Buyer.phone)))
                    .join(Meeting, Meeting.buyer_id == Buyer.id)
                    .filter(Meeting.seller_id == seller_uuid)
                    .filter(Meeting.start_time >= hour_start)
                    .filter(Meeting.start_time <= hour_end)
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
            
            # Calculate unique leads for the entire time period (fix double counting)
            total_unique_leads_corrected = (
                db.session.query(func.count(func.distinct(Buyer.phone)))
                .join(Meeting, Meeting.buyer_id == Buyer.id)
                .filter(Meeting.seller_id == seller_uuid)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .scalar() or 0
            )
        else:
            # Daily granularity
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
                    .filter(Meeting.seller_id == seller_uuid)
                    .filter(Meeting.direction == CallDirection.OUTGOING.value)
                    .filter(Meeting.start_time >= day_start)
                    .filter(Meeting.start_time <= day_end)
                    .count()
                )
                
                # Count incoming calls that resulted in meetings (answered)
                incoming_calls_answered_in_day = (
                    Meeting.query
                    .filter(Meeting.seller_id == seller_uuid)
                    .filter(Meeting.direction == CallDirection.INCOMING.value)
                    .filter(Meeting.start_time >= day_start)
                    .filter(Meeting.start_time <= day_end)
                    .count()
                )
                
                # Count unanswered outgoing calls from MobileAppCall table
                outgoing_calls_unanswered_in_day = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id == seller_uuid)
                    .filter(MobileAppCall.call_type == "outgoing")
                    .filter(MobileAppCall.status == MobileAppCallStatus.NOT_ANSWERED.value)
                    .filter(MobileAppCall.start_time >= day_start)
                    .filter(MobileAppCall.start_time <= day_end)
                    .count()
                )
                
                # Count incoming unanswered calls (missed and rejected) from MobileAppCall table
                incoming_calls_unanswered_in_day = (
                    MobileAppCall.query
                    .filter(MobileAppCall.user_id == seller_uuid)
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
                
                # Get unique buyer phone numbers only from Meeting table (actual conversations)
                # Only count buyers who had actual meetings/conversations
                unique_leads_in_day = (
                    db.session.query(func.count(func.distinct(Buyer.phone)))
                    .join(Meeting, Meeting.buyer_id == Buyer.id)
                    .filter(Meeting.seller_id == seller_uuid)
                    .filter(Meeting.start_time >= day_start)
                    .filter(Meeting.start_time <= day_end)
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
            
            # Calculate unique leads for the entire time period (fix double counting)
            total_unique_leads_corrected = (
                db.session.query(func.count(func.distinct(Buyer.phone)))
                .join(Meeting, Meeting.buyer_id == Buyer.id)
                .filter(Meeting.seller_id == seller_uuid)
                .filter(Meeting.start_time >= start_date)
                .filter(Meeting.start_time <= end_date)
                .scalar() or 0
            )
        
        result = {
            "seller_id": str(seller_uuid),
            "seller_name": seller.name,
            "seller_phone": seller.phone,
            "sales_data": sales_data,
            "total_data": {
                "total_outgoing_calls": total_outgoing_calls,
                "total_incoming_calls": total_incoming_calls,
                "total_calls": total_outgoing_calls + total_incoming_calls,
                "unique_leads_engaged": total_unique_leads_corrected
            }
        }
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Failed to fetch seller call data for seller {seller_uuid}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch seller call data: {str(e)}"}), 500
