import logging
import traceback

from flask import Blueprint, jsonify, request

from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db, Meeting, MobileAppCall
from app.services import SellerService
from app.constants import CallDirection
from app.models.seller import SellerRole
from sqlalchemy import func

from app.utils.call_recording_utils import denormalize_phone_number

logging = logging.getLogger(__name__)

user_bp = Blueprint("user", __name__)


@user_bp.route("/get_team", methods=["GET"])
@jwt_required()
def get_team():
    try:
        user_id = get_jwt_identity()
        user = SellerService.get_by_id(user_id)

        if not user:
            logging.error(f"Seller with id {user_id} not found")
            return jsonify({"error": "Seller not found"}), 404

        users = SellerService.get_by_agency(user.agency_id)
        all_members_total_outgoing_calls = 0
        all_members_total_incoming_calls = 0
        all_members_unanswered_outgoing_calls = 0
        all_members_unique_leads_engaged = 0
        all_members_unique_leads_called_but_not_engaged = 0

        team_members_list = []
        for team_member in users:
            total_outgoing_calls = (
                Meeting.query
                .filter(Meeting.seller_id == team_member.id)
                .filter(Meeting.direction == CallDirection.OUTGOING.value)
                .count()
            )
            total_incoming_calls = (
                Meeting.query
                .filter(Meeting.seller_id == team_member.id)
                .filter(Meeting.direction == CallDirection.INCOMING.value)
                .count()
            )
            unanswered_outgoing_calls = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id == team_member.id)
                .filter(MobileAppCall.status == 'Not Answered')
                .count()
            )
            unique_leads_engaged = (
                db.session.query(func.count(func.distinct(Meeting.buyer_id)))
                .filter(Meeting.seller_id == team_member.id)
                .scalar()
            )
            unique_leads_called_but_not_engaged = (
                db.session.query(func.count(func.distinct(MobileAppCall.buyer_number)))
                .filter(MobileAppCall.seller_number == team_member.phone)
                .scalar()
            )

            all_members_total_outgoing_calls += total_outgoing_calls
            all_members_total_incoming_calls += total_incoming_calls
            all_members_unanswered_outgoing_calls += unanswered_outgoing_calls
            all_members_unique_leads_engaged += unique_leads_engaged
            all_members_unique_leads_called_but_not_engaged += unique_leads_called_but_not_engaged

            team_members_list.append({
                "name": team_member.name,
                "email": team_member.email,
                "id": team_member.id,
                "phone": denormalize_phone_number(team_member.phone),
                "total_outgoing_calls": total_outgoing_calls,
                "total_incoming_calls": total_incoming_calls,
                "unanswered_outgoing_calls": unanswered_outgoing_calls,
                "unique_leads_engaged": unique_leads_engaged,
                "unique_leads_called": unique_leads_engaged + unique_leads_called_but_not_engaged
            })

        result = {
            "team_members": users,
            "total_outgoing_calls": all_members_total_outgoing_calls,
            "total_incoming_calls": all_members_total_incoming_calls,
            "total_unanswered_outgoing_calls": all_members_unanswered_outgoing_calls,
            "total_unique_leads_engaged": all_members_unique_leads_engaged,
            "total_unique_leads_called": all_members_unique_leads_engaged + all_members_unique_leads_called_but_not_engaged
        }

        return jsonify(result), 200
    except Exception as e:
        user_email = user.email if user else "unknown"
        logging.error(f"Failed to fetch team members for manager {user_email}, {user_id=}, with error: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify(f"Failed to fetch team members for user {user_id=}, with error: {e}")


# @user_bp.route("/get_call_analytics", methods=["GET"])
# @jwt_required()
# def get_call_analytics():
#     try:
#         user_id = get_jwt_identity()
#         user = Seller.query.filter_by(id=user_id).first()
#
#         if not user:
#             logging.error(f"Seller with id {user_id} not found")
#             return jsonify({"error": "Seller not found"}), 404
#
#         user_ids = request.args.getlist("user_id")
#         time_frame = request.args.get("time_frame", type=str)
#
#         # # If time_frame was provided, compute (start_dt,end_dt) or return 400
#         # if time_frame:
#         #     try:
#         #         start_dt, end_dt = compute_date_range(time_frame)
#         #     except ValueError as ve:
#         #         return jsonify({"error": str(ve)}), 400
#
#         if not user_ids:
#             return jsonify({"error": "Please select users for call analytics details"}), 400
#
#         # Ensure all requested users exist
#         for uid in user_ids:
#             if not Seller.query.get(uid):
#                 logging.error(f"Seller with id {uid} not found; unauthorized")
#                 return jsonify({"error": "Seller not found or unauthorized"}), 404
#
#         # Gather team members
#         users = Seller.query.filter(Seller.id.in_(user_ids)).all()
#
#         # Initialize totals
#         totals = {
#             "total_outgoing_calls": 0,
#             "total_incoming_calls": 0,
#             "total_unanswered_outgoing_calls": 0,
#             "total_unique_leads_engaged": 0,
#             "total_unique_leads_called": 0,
#         }
#
#         team_members_list = []
#
#         for member in users:
#             # --- OUTGOING CALLS ---
#             oq = Meeting.query.filter(
#                 Meeting.seller_number == member.phone,
#                 Meeting.direction == CallDirection.OUTGOING.value,
#             )
#             if time_frame:
#                 oq = oq.filter(Meeting.start_time >= start_dt,
#                                Meeting.start_time < end_dt)
#             total_out = oq.count()
#
#             # --- INCOMING CALLS ---
#             iq = Meeting.query.filter(
#                 Meeting.seller_number == member.phone,
#                 Meeting.direction == CallDirection.INCOMING.value,
#             )
#             if time_frame:
#                 iq = iq.filter(Meeting.start_time >= start_dt,
#                                Meeting.start_time < end_dt)
#             total_in = iq.count()
#
#             # --- UNANSWERED OUTGOING (MobileAppCall) ---
#             uoq = MobileAppCall.query.filter(
#                 MobileAppCall.user_id == member.id,
#                 MobileAppCall.status == "Not Answered",
#             )
#             if time_frame:
#                 uoq = uoq.filter(MobileAppCall.start_time >= start_dt,
#                                  MobileAppCall.start_time < end_dt)
#             unanswered = uoq.count()
#
#             # --- UNIQUE LEADS ENGAGED ---
#             uq_engaged_q = db.session.query(
#                 func.count(func.distinct(Meeting.buyer_number))
#             ).filter(
#                 Meeting.seller_number == member.phone
#             )
#             if time_frame:
#                 uq_engaged_q = uq_engaged_q.filter(Meeting.start_time >= start_dt,
#                                                    Meeting.start_time < end_dt)
#             unique_engaged = uq_engaged_q.scalar() or 0
#
#             # --- UNIQUE LEADS CALLED BUT NOT ENGAGED ---
#             uq_not_eng_q = db.session.query(
#                 func.count(func.distinct(MobileAppCall.buyer_number))
#             ).filter(
#                 MobileAppCall.seller_number == member.phone
#             )
#             if time_frame:
#                 uq_not_eng_q = uq_not_eng_q.filter(MobileAppCall.start_time >= start_dt,
#                                                    MobileAppCall.start_time < end_dt)
#             unique_not_engaged = uq_not_eng_q.scalar() or 0
#
#             # Accumulate totals
#             totals["total_outgoing_calls"] += total_out
#             totals["total_incoming_calls"] += total_in
#             totals["total_unanswered_outgoing_calls"] += unanswered
#             totals["total_unique_leads_engaged"] += unique_engaged
#             totals["total_unique_leads_called"] += (unique_engaged + unique_not_engaged)
#
#             # Per-member breakdown
#             team_members_list.append({
#                 "name": member.name,
#                 "email": member.email,
#                 "id": member.id,
#                 "phone": denormalize_phone_number(member.phone),
#                 "total_outgoing_calls": total_out,
#                 "total_incoming_calls": total_in,
#                 "unanswered_outgoing_calls": unanswered,
#                 "unique_leads_engaged": unique_engaged,
#                 "unique_leads_called": unique_engaged + unique_not_engaged,
#             })
#
#         # Build final payload
#         result = {
#             "users": [m.name for m in users],
#             **totals
#         }
#
#         return jsonify(result), 200
#
#     except Exception as e:
#         logging.error("Failed to fetch analytics data: %s", traceback.format_exc())
#         return jsonify({"error": f"Failed to fetch analytics data: {str(e)}"}), 500


@user_bp.route("/get_user", methods=["GET"])
@jwt_required()
def get_user():
    try:
        user_id = get_jwt_identity()
        user = SellerService.get_by_id(user_id)
        
        if not user:
            return jsonify({"error": "User not found"}), 404

        result = {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "phone": denormalize_phone_number(user.phone),
            "role": user.role.value,
            "last_week_performance_analysis": user.last_week_performance_analysis,
            "name": user.name,
        }

        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Failed to fetch user details: {e}")
        return jsonify({"error": f"Failed to fetch user details: {str(e)}"}), 500


@user_bp.route("/set_manager", methods=["POST"])
def assign_manager():
    try:
        data = request.get_json()
        user_email = data.get("user_email")
        manager_email = data.get("manager_email")
        logging.info(f"Assigning manager {manager_email} to user {user_email}")

        if not user_email or not manager_email:
            logging.error("Both manager_email and user_email are required data")
            return jsonify({"error": "Both manager_email and user_email are required data"}), 500

        user = SellerService.get_by_email(user_email)
        if not user:
            logging.error(f"Seller with email {user_email} not found")
            return jsonify({"error": "Seller with email {user_email} not found"}), 404

        manager = SellerService.get_by_email(manager_email)
        if not manager:
            logging.error(f"Manager with email {manager_email} not found")
            return jsonify({"error": f"Manager with email {manager_email} not found"})

        if not manager.role == SellerRole.MANAGER:
            logging.error(f"Seller with email {manager_email} is not a manager")
            return jsonify({"error": f"Seller with email {manager_email} is not a manager"})

        user.manager_id = manager.id
        db.session.commit()
        
        return jsonify({"message": "Manager assigned successfully"}), 200
    except Exception as e:
        logging.error(f"Failed to set manager {manager_email} for user {user_email}: {str(e)}")
        return jsonify({"error": f"Failed to set manager {manager_email} for user {user_email}: {str(e)}"})
