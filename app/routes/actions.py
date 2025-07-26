import logging
import traceback

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models.action import ActionStatus
from app.models.seller import SellerRole
from app.services import ActionService, SellerService

action_bp = Blueprint("actions", __name__)

logging = logging.getLogger(__name__)


@action_bp.route("/", methods=["GET"])
@jwt_required()
def get_actions():
    """
    Get actions for the current user or team members.
    
    Query parameters:
    - team_member_ids: List of team member IDs (managers only)
    - status: Filter by action status - 'pending' or 'completed' (optional)
    
    When status is provided, actions are sorted by creation date (newest first).
    When no status is provided, actions are sorted by due date (earliest first).
    """
    try:
        user_id = get_jwt_identity()
        team_member_ids = request.args.getlist("team_member_ids")
        status_param = request.args.get("status")

        # Authorization check for team member access
        if team_member_ids:
            user = SellerService.get_by_id(user_id)
            if not user:
                logging.error("User not found; unauthorized")
                return jsonify({"error": "User not found or unauthorized"}), 404
            if user.role != SellerRole.MANAGER:
                logging.info(f"Unauthorized User. 'team_member_ids' query parameter is only applicable for a manager.")
                return jsonify(
                    {"error": "Unauthorized User: 'team_member_ids' query parameter is only applicable for a manager"})

            # Validate team member IDs
            for member_id in team_member_ids:
                member = SellerService.get_by_id(member_id)
                if not member:
                    logging.error(f"Seller with id {member_id} not found; unauthorized")
                    return jsonify({"error": "Seller not found or unauthorized"}), 404

        # Parse and validate status parameter
        status_filter = None
        if status_param:
            status_param_lower = status_param.lower()
            if status_param_lower == "pending":
                status_filter = ActionStatus.PENDING
            elif status_param_lower == "completed":
                status_filter = ActionStatus.COMPLETED
            else:
                return jsonify({
                    "error": "Invalid status parameter. Must be 'pending' or 'completed'"
                }), 400

        # Use ActionService to get actions with optional status filter
        actions = ActionService.get_actions_for_user(user_id, team_member_ids, status_filter)
        
        response = {
            "actions": actions,
            "total_count": len(actions),
            "filtered_by_status": status_filter.value if status_filter else None
        }
        
        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Error fetching actions: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch actions"}), 500


@action_bp.route("/<uuid:action_id>", methods=["GET"])
@jwt_required()
def get_action_by_id(action_id: str):
    try:
        user_id = get_jwt_identity()

        # Check if user is a manager
        user = SellerService.get_by_id(user_id)
        if user and user.role == SellerRole.MANAGER:
            # Managers can access any action
            logging.info(f"Manager {user_id} accessing action {action_id}")
            action = ActionService.get_action_by_id(action_id)
        else:
            # Regular users can only access their own actions
            action = ActionService.get_action_by_id_for_user(action_id, user_id)
        
        if not action:
            return jsonify({"error": "Action not found or unauthorized"}), 404

        return jsonify(action), 200

    except Exception as e:
        logging.error(f"Error fetching action {action_id}: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch action"}), 500


@action_bp.route("/update", methods=["POST"])
@jwt_required()
def update_actions():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        if not data or not isinstance(data, list):
            return jsonify({"error": "Invalid request format. Expected array of actions."}), 400

        action_updates = []

        for item in data:
            action_id = item.get("id")
            status = item.get("status")

            if not action_id or not status:
                return jsonify({"error": "Missing required fields: id and status"}), 400

            if status not in [s.value for s in ActionStatus]:
                return jsonify({"error": f"Invalid status: {status}"}), 400

            action_updates.append({"id": action_id, "status": status})

        # Use ActionService for bulk update
        try:
            updated_count = ActionService.bulk_update_actions(action_updates, user_id)
            
            return jsonify({"message": f"Updated {updated_count} actions successfully"}), 200
            
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 404

    except Exception as e:
        logging.error(f"Error updating actions: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Failed to update actions"}), 500
