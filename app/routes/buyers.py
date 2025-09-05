import logging
import traceback
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services import BuyerService, BuyerSearchService, SellerService, MeetingService, ActionService
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

        # Parse pagination parameters
        page = request.args.get("page", type=int, default=1)
        limit = request.args.get("limit", type=int, default=50)
        
        # Validate pagination parameters
        if page < 1:
            return jsonify({"error": "Page number must be 1 or greater"}), 400
        if limit < 1 or limit > 100:
            return jsonify({"error": "Limit must be between 1 and 100"}), 400

        # Get current seller to determine agency
        seller = SellerService.get_by_id(user_id)
        if not seller:
            return jsonify({"error": "User not found"}), 404

        # Get buyers with last contact information for the seller's agency with pagination
        buyers_response = BuyerService.get_buyers_with_last_contact(str(seller.agency_id), page, limit)
        
        # Denormalize phone numbers for display
        for buyer in buyers_response["data"]:
            if buyer['phone']:
                buyer['phone'] = denormalize_phone_number(buyer['phone'])

        # Update response structure to match existing API format
        response = {
            "buyers": buyers_response["data"],
            "pagination": buyers_response["pagination"],
            "agency_id": str(seller.agency_id)
        }

        return jsonify(response), 200

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
    Accepts JSON with optional fields: risks, products_discussed, and key_highlights.
    """
    try:
        logging.info(f"Updating buyer profile for buyer_id {buyer_id}")

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Log raw data being sent for processing
        logging.info(f"[BUYER_UPDATE] Raw data received for buyer_id {buyer_id}: {data}")
        logging.info(f"[BUYER_UPDATE] Data keys: {list(data.keys())}")
        logging.info(f"[BUYER_UPDATE] Data types: {[(key, type(value).__name__) for key, value in data.items()]}")

        # Validate allowed fields
        allowed_fields = {'risks', 'products_discussed', 'key_highlights'}
        
        invalid_fields = set(data.keys()) - allowed_fields
        if invalid_fields:
            logging.warning(f"[BUYER_UPDATE] Invalid fields rejected for buyer_id {buyer_id}: {list(invalid_fields)}")
            return jsonify({"error": f"Invalid fields: {', '.join(invalid_fields)}"}), 400

        # Log validated data being processed
        logging.info(f"[BUYER_UPDATE] Validated data for buyer_id {buyer_id}: {data}")
        logging.info(f"[BUYER_UPDATE] Fields being updated: {list(data.keys())}")

        # Get buyer by ID and verify access
        buyer = BuyerService.get_by_id(buyer_id)
        if not buyer:
            logging.error(f"[BUYER_UPDATE] Buyer not found: {buyer_id}")
            return jsonify({"error": "Buyer not found"}), 404

        # Update buyer profile using BuyerService
        logging.info(f"[BUYER_UPDATE] Calling BuyerService.update_buyer_info with data: {data}")
        updated_buyer = BuyerService.update_buyer_info(buyer_id, **data)
        if not updated_buyer:
            logging.error(f"[BUYER_UPDATE] Failed to update buyer profile for buyer_id {buyer_id}")
            return jsonify({"error": "Failed to update buyer profile"}), 500

        logging.info(f"[BUYER_UPDATE] Successfully updated buyer profile for buyer_id {buyer_id}")

        # Calculate averaged interest levels from all meetings for response
        processed_products_discussed = BuyerService._calculate_averaged_products_discussed(buyer_id)

        # Return updated profile with averaged interest levels
        result = {
            "id": str(updated_buyer.id),
            "phone": denormalize_phone_number(updated_buyer.phone),
            "name": updated_buyer.name,
            "email": updated_buyer.email,
            "risks": updated_buyer.risks,
            "products_discussed": processed_products_discussed,  # Use averaged data
            "key_highlights": updated_buyer.key_highlights
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

        # Calculate averaged interest levels from all meetings instead of using stored data
        processed_products_discussed = BuyerService._calculate_averaged_products_discussed(buyer_id)
        
        # Return processed products_discussed data with interest_level
        result = {
            "id": str(buyer.id),
            "products_discussed": processed_products_discussed
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


@buyers_bp.route("/search", methods=["GET"])
@jwt_required()
def search_buyers():
    """
    Search buyers with fuzzy matching and suggestions.
    
    Query Parameters:
        - q (string, required): Search query (minimum 2 characters)
        - limit (integer, optional, default: 20, max: 50): Maximum results
        - suggestion_limit (integer, optional, default: 5): Maximum suggestions
    
    Returns:
        JSON response with search results, suggestions, and metadata
        
    Rate Limited: 10 searches per minute per user
    """
    try:
        user_id = get_jwt_identity()
        logging.info(f"Buyer search request from user {user_id}")

        # Get current seller to determine agency
        seller = SellerService.get_by_id(user_id)
        if not seller:
            return jsonify({"error": "User not found"}), 404

        # Get query parameters
        query = request.args.get("q", "").strip()
        limit = request.args.get("limit", type=int, default=20)
        suggestion_limit = request.args.get("suggestion_limit", type=int, default=5)
        
        # Validate query parameter
        if not query:
            return jsonify({"error": "Query parameter 'q' is required"}), 400
        
        # Validate limit parameters
        if limit < 1 or limit > 50:
            return jsonify({"error": "Limit must be between 1 and 50"}), 400
        
        if suggestion_limit < 0 or suggestion_limit > 10:
            return jsonify({"error": "Suggestion limit must be between 0 and 10"}), 400

        # Check rate limiting
        is_allowed, rate_info = BuyerSearchService.check_rate_limit(user_id)
        
        if not is_allowed:
            logging.warning(f"Search rate limit exceeded: user={user_id}")
            return jsonify({
                "error": "Search rate limit exceeded. Try again later.",
                "code": "RATE_LIMIT_EXCEEDED",
                "rate_limit": rate_info
            }), 429

        # Perform the search
        search_results = BuyerSearchService.search_buyers(
            query=query,
            agency_id=str(seller.agency_id),
            user_id=user_id,
            limit=limit,
            suggestion_limit=suggestion_limit
        )
        
        # Add rate limit info to response
        search_results["rate_limit"] = rate_info
        
        logging.info(f"Search completed: user={user_id}, query='{query}', "
                    f"results={search_results['total_count']}, "
                    f"time={search_results['search_time_ms']}ms")

        return jsonify(search_results), 200

    except Exception as e:
        logging.error(f"Failed to search buyers for user {user_id}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": "Search service temporarily unavailable",
            "code": "SEARCH_SERVICE_ERROR"
        }), 500


@buyers_bp.route("/create", methods=["POST"])
@jwt_required()
def create_buyer():
    """
    Create a new buyer for the current seller's agency.
    Accepts JSON with required fields: name, phone, and optional fields: email, company_name, etc.
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
        
        risks = data.get('risks')
        products_discussed = data.get('products_discussed')
        key_highlights = data.get('key_highlights')

        # Create buyer using BuyerService
        new_buyer = BuyerService.create_buyer(
            phone=phone,
            agency_id=str(seller.agency_id),
            name=name,
            email=email,
            company_name=company_name,
            risks=risks,
            products_discussed=products_discussed,
            key_highlights=key_highlights
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
            "risks": new_buyer.risks,
            "products_discussed": new_buyer.products_discussed,
            "key_highlights": new_buyer.key_highlights
        }

        return jsonify({
            "message": "Buyer created successfully",
            "buyer": result
        }), 201

    except Exception as e:
        logging.error(f"Failed to create buyer for user {user_id}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to create buyer: {str(e)}"}), 500
