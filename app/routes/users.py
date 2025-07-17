import logging
import traceback

from flask import Blueprint, jsonify, request

from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.services import SellerService
from app.models.seller import SellerRole

from app.utils.call_recording_utils import denormalize_phone_number

logging = logging.getLogger(__name__)

user_bp = Blueprint("user", __name__)


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
