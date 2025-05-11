import json
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import Meeting, db
from app.models.action import Action, ActionStatus
from app.models.deal import Deal

logging = logging.getLogger(__name__)

action_bp = Blueprint("action", __name__)


@action_bp.route("/get_actions", methods=["GET"])
@jwt_required()
def get_actions():
    try:
        user_id = get_jwt_identity()

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
                "type": action.type.value
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
            "type": action.type.value
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
        actions = (
            Action.query
            .join(Action.meeting)
            .join(Meeting.deal)
            .filter(Action.id.in_(action_ids), Deal.user_id == user_id)
            .all()
        )

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
