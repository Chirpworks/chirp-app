import traceback

import logging

from flask import Blueprint, jsonify, request

from flask_jwt_extended import get_jwt_identity, jwt_required

from app import User, db, Meeting, Deal, MobileAppCall
from app.constants import CallDirection
from app.models.user import UserRole
from sqlalchemy import func

from app.utils.call_recording_utils import denormalize_phone_number
from app.utils.utils import compute_date_range

logging = logging.getLogger(__name__)

user_bp = Blueprint("user", __name__)


@user_bp.route("/get_users", methods=["GET"])
@jwt_required()
def get_team():
    try:
        user_id = get_jwt_identity()
        user = User.query.filter_by(id=user_id).first()

        if not user:
            logging.error(f"User with id {user_id} not found")
            return jsonify({"error": "User not found"}), 404

        users = (
            User.query
            .filter(User.agency_id == user.agency_id)
        )

        team_members_list = []
        for team_member in users:
            team_members_list.append({
                "name": team_member.name,
                "email": team_member.email,
                "id": team_member.id,
                "phone": denormalize_phone_number(team_member.phone),
            })

        result = {
            "users": team_members_list,
        }

        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Failed to get all users for user {user.email}, {user_id=}, "
                      f"    with error trace: {traceback.format_exc()}")
        return jsonify(f"Failed to fetch team members for user {user_id=}, with error: {e}")


@user_bp.route("/get_call_analytics", methods=["GET"])
@jwt_required()
def get_call_analytics():
    try:
        user_id = get_jwt_identity()
        user = User.query.filter_by(id=user_id).first()

        if not user:
            logging.error(f"User with id {user_id} not found")
            return jsonify({"error": "User not found"}), 404

        user_ids = request.args.getlist("user_id")
        time_frame = request.args.get("time_frame", type=str)

        # If time_frame was provided, compute (start_dt,end_dt) or return 400
        if time_frame:
            try:
                start_dt, end_dt = compute_date_range(time_frame)
            except ValueError as ve:
                return jsonify({"error": str(ve)}), 400

        if not user_ids:
            return jsonify({"error": "Please select users for call analytics details"}), 400

        # Ensure all requested users exist
        for uid in user_ids:
            if not User.query.get(uid):
                logging.error(f"User with id {uid} not found; unauthorized")
                return jsonify({"error": "User not found or unauthorized"}), 404

        # Gather team members
        users = User.query.filter(User.id.in_(user_ids)).all()

        # Initialize totals
        totals = {
            "total_outgoing_calls": 0,
            "total_incoming_calls": 0,
            "total_unanswered_outgoing_calls": 0,
            "total_unique_leads_engaged": 0,
            "total_unique_leads_called": 0,
        }

        team_members_list = []

        for member in users:
            # --- OUTGOING CALLS ---
            oq = Meeting.query.filter(
                Meeting.seller_number == member.phone,
                Meeting.direction == CallDirection.OUTGOING.value,
            )
            if time_frame:
                oq = oq.filter(Meeting.start_time >= start_dt,
                               Meeting.start_time < end_dt)
            total_out = oq.count()

            # --- INCOMING CALLS ---
            iq = Meeting.query.filter(
                Meeting.seller_number == member.phone,
                Meeting.direction == CallDirection.INCOMING.value,
            )
            if time_frame:
                iq = iq.filter(Meeting.start_time >= start_dt,
                               Meeting.start_time < end_dt)
            total_in = iq.count()

            # --- UNANSWERED OUTGOING (MobileAppCall) ---
            uoq = MobileAppCall.query.filter(
                MobileAppCall.user_id == member.id,
                MobileAppCall.status == "Not Answered",
            )
            if time_frame:
                uoq = uoq.filter(MobileAppCall.start_time >= start_dt,
                                 MobileAppCall.start_time < end_dt)
            unanswered = uoq.count()

            # --- UNIQUE LEADS ENGAGED ---
            uq_engaged_q = db.session.query(
                func.count(func.distinct(Meeting.buyer_number))
            ).filter(
                Meeting.seller_number == member.phone
            )
            if time_frame:
                uq_engaged_q = uq_engaged_q.filter(Meeting.start_time >= start_dt,
                                                   Meeting.start_time < end_dt)
            unique_engaged = uq_engaged_q.scalar() or 0

            # --- UNIQUE LEADS CALLED BUT NOT ENGAGED ---
            uq_not_eng_q = db.session.query(
                func.count(func.distinct(MobileAppCall.buyer_number))
            ).filter(
                MobileAppCall.seller_number == member.phone
            )
            if time_frame:
                uq_not_eng_q = uq_not_eng_q.filter(MobileAppCall.start_time >= start_dt,
                                                   MobileAppCall.start_time < end_dt)
            unique_not_engaged = uq_not_eng_q.scalar() or 0

            # Accumulate totals
            totals["total_outgoing_calls"] += total_out
            totals["total_incoming_calls"] += total_in
            totals["total_unanswered_outgoing_calls"] += unanswered
            totals["total_unique_leads_engaged"] += unique_engaged
            totals["total_unique_leads_called"] += (unique_engaged + unique_not_engaged)

            # Per-member breakdown
            team_members_list.append({
                "name": member.name,
                "email": member.email,
                "id": member.id,
                "phone": denormalize_phone_number(member.phone),
                "total_outgoing_calls": total_out,
                "total_incoming_calls": total_in,
                "unanswered_outgoing_calls": unanswered,
                "unique_leads_engaged": unique_engaged,
                "unique_leads_called": unique_engaged + unique_not_engaged,
            })

        # Build final payload
        result = {
            "users": [m.name for m in users],
            **totals
        }

        return jsonify(result), 200

    except Exception as e:
        logging.error("Failed to fetch analytics data: %s", traceback.format_exc())
        return jsonify({"error": f"Failed to fetch analytics data: {str(e)}"}), 500


@user_bp.route("/get_user", methods=["GET"])
@jwt_required()
def get_user():
    try:
        user_id = get_jwt_identity()
        user = User.query.filter_by(id=user_id).first()

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
        logging.error(f"Failed to fetch user details: {traceback.format_exc()}")
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

        user = User.query.filter_by(email=user_email).first()
        if not user:
            logging.error(f"User with email {user_email} not found")
            return jsonify({"error": "User with email {user_email} not found"}), 404

        manager = User.query.filter_by(email=manager_email).first()
        if not manager:
            logging.error(f"Manager with email {manager_email} not found")
            return jsonify({"error": f"Manager with email {manager_email} not found"})

        if not manager.role == UserRole.MANAGER:
            logging.error(f"User with email {manager_email} is not a manager")
            return jsonify({"error": f"User with email {manager_email} is not a manager"})

        user.manager_id = manager.id
        db.session.commit()
    except Exception as e:
        logging.error(f"Failed to set manager {manager_email} for user {user_email}: {str(traceback.format_exc())}")
        return jsonify({"error": f"Failed to set manager {manager_email} for user {user_email}: {str(e)}"})
