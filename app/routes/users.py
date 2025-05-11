import logging

from flask import Blueprint, jsonify

from flask_jwt_extended import get_jwt_identity, jwt_required

from app import User

logging = logging.getLogger(__name__)

user_bp = Blueprint("user", __name__)


@user_bp.route("/", methods=["GET"])
def get_users():
    return jsonify({"message": "List of users"})


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
        logging.error(f"Failed to getch user details: {e}")
        return jsonify({"error": f"Failed to fetch user details: {str(e)}"}), 500
