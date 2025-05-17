import json
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import Meeting, db, User
from app.models.action import Action, ActionStatus, ActionType
from app.models.deal import Deal
from app.models.user import UserRole

logging = logging.getLogger(__name__)

action_bp = Blueprint("action", __name__)


@action_bp.route("/get_actions", methods=["GET"])
@jwt_required()
def get_actions():
    try:
        user_id = get_jwt_identity()

        if not user_id:
            logging.error("Failed to get action - Unauthorized")
            return jsonify({"error": "User not found or unauthorized"}), 401

        team_member_id = request.args.get("team_member_id")
        if team_member_id:
            user = User.query.filter_by(id=user_id).first()
            if not user:
                logging.error("User not found; unauthorized")
                return jsonify({"error": "User not found or unauthorized"}), 404
            if user.role != UserRole.MANAGER:
                logging.info(f"Unauthorized User. 'team_member_id' query parameter is only applicable for a manager.")
                return jsonify(
                    {"error": "Unauthorized User: 'team_member_id' query parameter is only applicable for a manager"}
                )
            logging.info(f"setting user_id to {team_member_id=} for manager_id={user_id}")
            user_id = team_member_id

        logging.info(f"Fetching actions data for user {user_id}")

        action_type = request.args.get("actionType")

        # Parse optional query params
        deal_id = request.args.get("deal_id")
        is_complete_str = request.args.get("is_complete")
        is_complete = None

        if is_complete_str is not None:
            is_complete = is_complete_str.lower() == "true"

        # Base query: actions joined through meetings and deals
        query = (
            Action.query
            .join(Action.meeting)
            .join(Meeting.deal)
            .filter(Deal.user_id == user_id)
        )

        if deal_id:
            query = query.filter(Meeting.deal_id == deal_id)

        if action_type:
            query = query.filter(Action.type == action_type)

        if is_complete is True:
            query = query.filter(Action.status == ActionStatus.COMPLETED)
        elif is_complete is False:
            query = query.filter(Action.status == ActionStatus.PENDING)

        actions = query.all()

        # Prepare response
        result = []
        for action in actions:
            is_complete = True if action.status == ActionStatus.COMPLETED else False
            result.append({
                "id": str(action.id),
                "title": action.title,
                "status": action.status.value,
                "is_complete": is_complete,
                "due_date": action.due_date.isoformat() if action.due_date else None,
                "description": action.description,
                "deal_name": action.meeting.deal.name,
                "deal_id": str(action.meeting.deal_id),
                "reasoning": action.reasoning,
                "signals": action.signals,
                "type": action.type.value,
                "created_at": action.created_at,
                "meeting_id": action.meeting_id
            })

        return jsonify(result), 200

    except Exception as e:
        logging.info(f"Failed to fetch actions with error: {e}")
        return jsonify({"error": f"Failed to fetch actions: {str(e)}"}), 500


@action_bp.route("/get_action_details/<uuid:action_id>", methods=["GET"])
@jwt_required()
def get_action_by_id(action_id):
    try:
        user_id = get_jwt_identity()

        if not user_id:
            logging.error("Failed to get action - Unauthorized")
            return jsonify({"error": "User not found or unauthorized"}), 401

        team_member_id = request.args.get("team_member_id")
        if team_member_id:
            user = User.query.filter_by(id=user_id).first()
            if not user:
                logging.error("User not found; unauthorized")
                return jsonify({"error": "User not found or unauthorized"}), 404
            if user.role != UserRole.MANAGER:
                logging.info(f"Unauthorized User. 'team_member_id' query parameter is only applicable for a manager.")
                return jsonify(
                    {"error": "Unauthorized User: 'team_member_id' query parameter is only applicable for a manager"}
                )
            logging.info(f"setting user_id to {team_member_id=} for manager_id={user_id}")
            user_id = team_member_id

        logging.info(f"Fetching actions data for user {user_id}")

        # Join to verify ownership through deal
        action = (
            Action.query
            .join(Action.meeting)
            .join(Meeting.deal)
            .filter(Action.id == action_id, Deal.user_id == user_id)
            .first()
        )

        if not action:
            return jsonify({"error": "Action not found or unauthorized"}), 404
        if not user_id:
            return jsonify({"error": "User not found or unauthorized"}), 401

        is_complete = action.status == ActionStatus.COMPLETED
        result = {
            "id": str(action.id),
            "title": action.title,
            "status": action.status.value,
            "is_complete": is_complete,
            "due_date": action.due_date.isoformat() if action.due_date else None,
            "description": action.description,
            "deal_name": action.meeting.deal.name,
            "deal_id": str(action.meeting.deal_id),
            "reasoning": action.reasoning,
            "signals": action.signals,
            "type": action.type.value,
            "created_at": action.created_at,
            "meeting_id": action.meeting_id
        }

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Failed to fetch action details: {e}")
        return jsonify({"error": f"Failed to fetch action: {str(e)}"}), 500


@action_bp.route("/status", methods=["POST"])
@jwt_required()
def update_multiple_action_statuses():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        action_ids = data.get("action_ids")
        status_str = data.get("status")

        if not action_ids or not isinstance(action_ids, list) or not status_str:
            return jsonify({"error": "Request must include 'action_ids' (list) and 'status'"}), 400

        try:
            new_status = ActionStatus[status_str.upper()]
        except KeyError:
            return jsonify({"error": "Invalid status. Must be 'pending' or 'completed'"}), 400

        # Fetch and filter actions that belong to this user
        query = (
            Action.query
            .join(Action.meeting)
            .join(Meeting.deal)
            .filter(Action.id.in_(action_ids), Deal.user_id == user_id)
        )

        actions = query.all()

        if not actions:
            return jsonify({"error": "No valid actions found for current user"}), 404

        if not user_id:
            return jsonify({"error": "User not found or unauthorized"}), 401

        updated_ids = []
        for action in actions:
            action.status = new_status
            updated_ids.append(str(action.id))

        db.session.commit()

        return jsonify({
            "message": f"Updated status for {len(updated_ids)} actions",
            "updated_action_ids": updated_ids,
            "new_status": new_status.value
        }), 200

    except Exception as e:
        logging.error(f"Failed to change action status: {e}")
        db.session.rollback()
        return jsonify({"error": f"Failed to update actions: {str(e)}"}), 500


@action_bp.route("/update_action_type", methods=["POST"])
@jwt_required()
def update_action_type():
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "User not found or unauthorized"}), 401

        data = request.get_json()

        action_id = data.get("action_id")
        action_type = data.get("action_type")

        if not action_id or not action_type:
            return jsonify({"error": "Request must include 'action_id' and 'action_type'"}), 400

        try:
            new_type = ActionType[action_type.upper()]
        except KeyError:
            return jsonify({"error": "Invalid status. Must be 'suggested_action' or 'contextual_action'"}), 400

        action = Action.query.filter(Action.id==action_id).first()
        if not action:
            return jsonify({"error": f"No valid action found for action_id: {action_id}"}), 404

        action.type = new_type

        db.session.commit()

        return jsonify({
            "message": f"Updated type for action {action_id}",
            "new_type": new_type.value
        }), 200

    except Exception as e:
        logging.error(f"Failed to change action type: {e}")
        db.session.rollback()
        return jsonify({"error": f"Failed to update action type: {str(e)}"}), 500
