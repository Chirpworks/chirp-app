import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services import BuyerService, SellerService, MeetingService
from app.models.seller import SellerRole
from app.utils.call_recording_utils import denormalize_phone_number

buyers_bp = Blueprint("buyers", __name__)

logging = logging.getLogger(__name__)


@buyers_bp.route("/profile/<uuid:buyer_id>", methods=["GET"])
def get_buyer_profile(buyer_id):
    """
    Fetch buyer profile by buyer ID.
    Returns all buyer fields except meetings, actions, and agency.
    """
    try:
        logging.info(f"Fetching buyer profile for buyer_id {buyer_id}")

        # Get buyer by ID
        buyer = BuyerService.get_by_id(buyer_id)
        if not buyer:
            return jsonify({"error": "Buyer not found"}), 404

        # Build response with all fields except meetings, actions, and agency
        result = {
            "id": str(buyer.id),
            "phone": denormalize_phone_number(buyer.phone),
            "name": buyer.name,
            "email": buyer.email,
            "tags": buyer.tags,
            "requirements": buyer.requirements,
            "solutions_presented": buyer.solutions_presented,
            "relationship_progression": buyer.relationship_progression,
            "risks": buyer.risks,
            "products_discussed": buyer.products_discussed
        }

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Failed to fetch buyer profile for buyer_id {buyer_id}: {e}")
        return jsonify({"error": f"Failed to fetch buyer profile: {str(e)}"}), 500


@buyers_bp.route("/call_history/<uuid:buyer_id>", methods=["GET"])
@jwt_required()
def get_buyer_call_history(buyer_id):
    """
    Fetch call history for a specific buyer.
    Returns all calls (meetings and mobile app calls) associated with the buyer.
    """
    try:
        logging.info(f"Fetching call history for buyer_id {buyer_id}")

        # Get buyer by ID and verify access
        buyer = BuyerService.get_by_id(buyer_id)
        if not buyer:
            return jsonify({"error": "Buyer not found"}), 404

        # Get call history using MeetingService
        call_history = MeetingService.get_call_history_by_buyer(buyer_id)

        return jsonify(call_history), 200

    except Exception as e:
        logging.error(f"Failed to fetch call history for buyer_id {buyer_id}: {e}")
        return jsonify({"error": f"Failed to fetch call history: {str(e)}"}), 500


@buyers_bp.route("/profile/<uuid:buyer_id>", methods=["PUT"])
def update_buyer_profile(buyer_id):
    """
    Update buyer profile with provided data.
    Accepts JSON with optional fields: tags, requirements, solutions_presented, 
    relationship_progression, risks, and products_discussed.
    """
    try:
        logging.info(f"Updating buyer profile for buyer_id {buyer_id}")

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate allowed fields
        allowed_fields = {
            'tags', 'requirements', 'solutions_presented', 
            'relationship_progression', 'risks', 'products_discussed'
        }
        
        invalid_fields = set(data.keys()) - allowed_fields
        if invalid_fields:
            return jsonify({"error": f"Invalid fields: {', '.join(invalid_fields)}"}), 400

        # Get buyer by ID and verify access
        buyer = BuyerService.get_by_id(buyer_id)
        if not buyer:
            return jsonify({"error": "Buyer not found"}), 404

        # Update buyer profile using BuyerService
        updated_buyer = BuyerService.update_buyer_info(buyer_id, **data)
        if not updated_buyer:
            return jsonify({"error": "Failed to update buyer profile"}), 500

        # Return updated profile
        result = {
            "id": str(updated_buyer.id),
            "phone": denormalize_phone_number(updated_buyer.phone),
            "name": updated_buyer.name,
            "email": updated_buyer.email,
            "tags": updated_buyer.tags,
            "requirements": updated_buyer.requirements,
            "solutions_presented": updated_buyer.solutions_presented,
            "relationship_progression": updated_buyer.relationship_progression,
            "risks": updated_buyer.risks,
            "products_discussed": updated_buyer.products_discussed
        }

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Failed to update buyer profile for buyer_id {buyer_id}: {e}")
        return jsonify({"error": f"Failed to update buyer profile: {str(e)}"}), 500


@buyers_bp.route("/product_catalogue/<uuid:buyer_id>", methods=["GET"])
def get_buyer_products_catalogue(buyer_id):
    """
    Fetch products catalogue for a specific buyer.
    Returns only the products_discussed data from the buyer table.
    """
    try:
        logging.info(f"Fetching products catalogue for buyer_id {buyer_id}")

        # Get buyer by ID
        buyer = BuyerService.get_by_id(buyer_id)
        if not buyer:
            return jsonify({"error": "Buyer not found"}), 404

        # Return only the products_discussed data
        result = {
            "id": str(buyer.id),
            "products_discussed": buyer.products_discussed
        }

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Failed to fetch products catalogue for buyer_id {buyer_id}: {e}")
        return jsonify({"error": f"Failed to fetch products catalogue: {str(e)}"}), 500
