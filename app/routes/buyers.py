import logging
import traceback
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services import BuyerService, SellerService, MeetingService, ActionService
from app.utils.call_recording_utils import denormalize_phone_number

buyers_bp = Blueprint("buyers", __name__)

logging = logging.getLogger(__name__)


@buyers_bp.route("/all", methods=["GET"])
@jwt_required()
def get_agency_buyers():
    """
    Get all buyers from the current seller's agency.
    Returns buyers sorted by last contacted date with contact information.
    """
    try:
        user_id = get_jwt_identity()
        logging.info(f"Fetching agency buyers for user {user_id}")

        # Get current seller to determine agency
        seller = SellerService.get_by_id(user_id)
        if not seller:
            return jsonify({"error": "User not found"}), 404

        # Get buyers with last contact information for the seller's agency
        buyers = BuyerService.get_buyers_with_last_contact(str(seller.agency_id))
        
        # Denormalize phone numbers for display
        for buyer in buyers:
            if buyer['phone']:
                buyer['phone'] = denormalize_phone_number(buyer['phone'])

        return jsonify({
            "buyers": buyers,
            "total_count": len(buyers),
            "agency_id": str(seller.agency_id)
        }), 200

    except Exception as e:
        logging.error(f"Failed to fetch agency buyers for user {user_id}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch agency buyers: {str(e)}"}), 500


@buyers_bp.route("/profile/<uuid:buyer_id>", methods=["GET"])
def get_buyer_profile(buyer_id):
    """
    Fetch buyer profile by buyer ID.
    Returns all buyer fields except meetings, actions, and agency, plus last contact information.
    """
    try:
        logging.info(f"Fetching buyer profile for buyer_id {buyer_id}")

        # Get buyer with last contact information
        buyer_data = BuyerService.get_buyer_with_last_contact(str(buyer_id))
        if not buyer_data:
            return jsonify({"error": "Buyer not found"}), 404

        # Denormalize phone number for display
        if buyer_data['phone']:
            buyer_data['phone'] = denormalize_phone_number(buyer_data['phone'])

        return jsonify(buyer_data), 200

    except Exception as e:
        logging.error(f"Failed to fetch buyer profile for buyer_id {buyer_id}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch buyer profile: {str(e)}"}), 500


@buyers_bp.route("/call_history/<uuid:buyer_id>", methods=["GET"])
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
        logging.error(f"Traceback: {traceback.format_exc()}")
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
        logging.error(f"Traceback: {traceback.format_exc()}")
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
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch products catalogue: {str(e)}"}), 500


@buyers_bp.route("/actions/count/<uuid:buyer_id>", methods=["GET"])
def get_buyer_pending_actions_count(buyer_id):
    """
    Get the count of pending actions for a specific buyer.
    Returns a simple number representing the count of pending actions.
    """
    try:
        logging.info(f"Fetching pending actions count for buyer_id {buyer_id}")

        # Verify buyer exists
        buyer = BuyerService.get_by_id(buyer_id)
        if not buyer:
            return jsonify({"error": "Buyer not found"}), 404

        # Get pending actions count
        pending_count = ActionService.get_pending_actions_count_for_buyer(str(buyer_id))

        return jsonify({
            "buyer_id": str(buyer_id),
            "pending_actions_count": pending_count
        }), 200

    except Exception as e:
        logging.error(f"Failed to fetch pending actions count for buyer_id {buyer_id}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch pending actions count: {str(e)}"}), 500


@buyers_bp.route("/actions/<uuid:buyer_id>", methods=["GET"])
def get_buyer_actions(buyer_id):
    """
    Get all actions for a specific buyer.
    Returns actions sorted with PENDING actions first (by due_date ascending), 
    followed by COMPLETED actions (by due_date ascending).
    """
    try:
        logging.info(f"Fetching all actions for buyer_id {buyer_id}")

        # Verify buyer exists
        buyer = BuyerService.get_by_id(buyer_id)
        if not buyer:
            return jsonify({"error": "Buyer not found"}), 404

        # Get all actions for the buyer
        actions = ActionService.get_all_actions_for_buyer(str(buyer_id))

        return jsonify({
            "buyer_id": str(buyer_id),
            "actions": actions,
            "total_count": len(actions)
        }), 200

    except Exception as e:
        logging.error(f"Failed to fetch actions for buyer_id {buyer_id}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch actions: {str(e)}"}), 500


@buyers_bp.route("/create", methods=["POST"])
@jwt_required()
def create_buyer():
    """
    Create a new buyer for the current seller's agency.
    Accepts JSON with required fields: name, phone, and optional fields: email, company_name, tags, etc.
    """
    try:
        user_id = get_jwt_identity()
        logging.info(f"Creating buyer for user {user_id}")

        # Get current seller to determine agency
        seller = SellerService.get_by_id(user_id)
        if not seller:
            return jsonify({"error": "User not found"}), 404

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Extract required fields
        name = data.get('name')
        phone = data.get('phone')
        
        # Validate required fields
        if not name or not phone:
            return jsonify({"error": "Missing required fields: name and phone are required"}), 400

        # Extract optional fields
        email = data.get('email')
        company_name = data.get('company_name')
        tags = data.get('tags', [])
        requirements = data.get('requirements')
        solutions_presented = data.get('solutions_presented')
        relationship_progression = data.get('relationship_progression')
        risks = data.get('risks')
        products_discussed = data.get('products_discussed')

        # Create buyer using BuyerService
        new_buyer = BuyerService.create_buyer(
            phone=phone,
            agency_id=str(seller.agency_id),
            name=name,
            email=email,
            company_name=company_name,
            tags=tags,
            requirements=requirements,
            solutions_presented=solutions_presented,
            relationship_progression=relationship_progression,
            risks=risks,
            products_discussed=products_discussed
        )

        logging.info(f"Created buyer successfully: {new_buyer.id} for agency: {seller.agency_id}")
        
        # Return created buyer data
        result = {
            "id": str(new_buyer.id),
            "name": new_buyer.name,
            "phone": denormalize_phone_number(new_buyer.phone),
            "email": new_buyer.email,
            "company_name": new_buyer.company_name,
            "agency_id": str(seller.agency_id),
            "tags": new_buyer.tags,
            "requirements": new_buyer.requirements,
            "solutions_presented": new_buyer.solutions_presented,
            "relationship_progression": new_buyer.relationship_progression,
            "risks": new_buyer.risks,
            "products_discussed": new_buyer.products_discussed
        }

        return jsonify({
            "message": "Buyer created successfully",
            "buyer": result
        }), 201

    except Exception as e:
        logging.error(f"Failed to create buyer for user {user_id}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to create buyer: {str(e)}"}), 500
