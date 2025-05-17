import logging

from flask import Blueprint, jsonify, request

from flask_jwt_extended import get_jwt_identity, jwt_required

from app import User, db
from app.models.user import UserRole

logging = logging.getLogger(__name__)

user_bp = Blueprint("user", __name__)


@user_bp.route("/get_manager_team", methods=["GET"])
@jwt_required()
def get_users():
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

        result = []
        for team_member in team_members:
            result.append({
                "name": team_member.name,
                "email": team_member.email,
                "id": team_member.id
            })

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
            "phone": user.phone,
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
