import logging

from flask import Blueprint, jsonify, request

from flask_jwt_extended import get_jwt_identity, jwt_required

from app import User, db, Meeting, Deal, MobileAppCall
from app.constants import CallDirection
from app.models.user import UserRole
from sqlalchemy import func

from app.utils.call_recording_utils import denormalize_phone_number

logging = logging.getLogger(__name__)

user_bp = Blueprint("user", __name__)


@user_bp.route("/get_team", methods=["GET"])
@jwt_required()
def get_team():
    try:
        user_id = get_jwt_identity()
        user = User.query.filter_by(id=user_id).first()

        if not user:
            logging.error(f"User with id {user_id} not found")
            return jsonify({"error": "User not found"}), 404

        if user.role != UserRole.MANAGER:
            logging.error(
                f"User with email {user.email} has assigned role {user.role.value}. User with manager role required"
            )
            return jsonify({"error": "Unauthorized Access. Login using a Manager Account."}), 401

        team_members = (
            User.query
            .filter(User.manager_id == user.id)
        )
        all_members_total_outgoing_calls = 0
        all_members_total_incoming_calls = 0
        all_members_unanswered_outgoing_calls = 0
        all_members_unique_leads_engaged = 0
        all_members_unique_leads_called_but_not_engaged = 0

        team_members_list = []
        for team_member in team_members:
            total_outgoing_calls = (
                Meeting.query
                .filter(Meeting.seller_number == team_member.phone)
                .filter(Meeting.direction == CallDirection.OUTGOING.value)
                .scalar()
            )
            total_incoming_calls = (
                Meeting.query
                .filter(Meeting.seller_number == team_member.phone)
                .filter(Meeting.direction == CallDirection.INCOMING.value)
                .scalar()
            )
            unanswered_outgoing_calls = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id == team_member.id)
                .filter(MobileAppCall.status == 'Not Answered')
                .scalar()
            )
            unique_leads_engaged = (
                db.session.query(func.count(func.distinct(Meeting.buyer_number)))
                .filter(Meeting.seller_number == team_member.phone)
                .scalar()
            )
            unique_leads_called_but_not_engaged = (
                db.session.query(func.count(func.ditinct(MobileAppCall.buyer_number)))
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
            "team_members": team_members,
            "total_outgoing_calls": all_members_total_outgoing_calls,
            "total_incoming_calls": all_members_total_incoming_calls,
            "total_unanswered_outgoing_calls": all_members_unanswered_outgoing_calls,
            "total_unique_leads_engaged": all_members_unique_leads_engaged,
            "total_unique_leads_called": all_members_unique_leads_engaged + all_members_unique_leads_called_but_not_engaged
        }

        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Failed to fetch team members for manager {user.email}, {user_id=}, with error: {e}")
        return jsonify(f"Failed to fetch team members for user {user_id=}, with error: {e}")


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
        logging.error(f"Failed to set manager {manager_email} for user {user_email}: {str(e)}")
        return jsonify({"error": f"Failed to set manager {manager_email} for user {user_email}: {str(e)}"})
