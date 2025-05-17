import json
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import func

from app import Meeting, db, User
from app.models.action import Action, ActionStatus
from app.models.deal import Deal
from app.models.user import UserRole

logging = logging.getLogger(__name__)

deals_bp = Blueprint("deal", __name__)


@deals_bp.route("/get_deals", methods=["GET"])
@jwt_required()
def get_deals():
    try:
        user_id = get_jwt_identity()

        deal_id = request.args.get("dealId")
        team_member_ids = request.args.getlist("team_member_id")
        if team_member_ids:
            user = User.query.filter_by(id=user_id).first()
            if not user:
                logging.error("User not found; unauthorized")
                return jsonify({"error": "User not found or unauthorized"}), 404
            if user.role != UserRole.MANAGER:
                logging.info(f"Unauthorized User. 'team_member_id' query parameter is only applicable for a manager.")
                return jsonify(
                    {"error": "Unauthorized User: 'team_member_id' query parameter is only applicable for a manager"}
                )

            logging.info(f"Fetching call history for users {team_member_ids}")

            query = (
                Deal.query
                .filter(Deal.user_id.in_(team_member_ids))
            )
        else:
            # Base query: actions joined through meetings and deals
            query = (
                Deal.query
                .filter(Deal.user_id == user_id)
            )

        if deal_id:
            query = query.filter(Deal.id == deal_id)
        deals = query.all()

        # Prepare response
        result = []
        for deal in deals:
            num_pending_actions = (
                db.session.query(func.count(Action.id))
                .join(Meeting, Action.meeting_id == Meeting.id)
                .join(Deal, Meeting.deal_id == Deal.id)
                .filter(Deal.id == deal.id)
                .filter(Action.status == ActionStatus.PENDING)
                .scalar()
            )
            last_contacted_on = (
                db.session.query(func.max(Meeting.start_time))
                .filter(Meeting.deal_id == deal.id)
                .scalar()
            )
            result.append({
                "id": str(deal.id),
                "name": deal.name,
                "stage": deal.stage,
                "lead_qualification": deal.lead_qualification,
                "overview": deal.overview,
                "key_stakeholders": deal.key_stakeholders,
                "buyer_number": deal.buyer_number,
                "seller_number": deal.seller_number,
                "summary": deal.summary,
                "num_pending_actions": num_pending_actions,
                "last_contacted_on": last_contacted_on,
                "user_name": deal.user.name,
                "user_email": deal.user.email
            })

        result = sorted(result, key=lambda x: x["last_contacted_on"], reverse=True)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": f"Failed to fetch actions: {str(e)}"}), 500


@deals_bp.route("/deal_details/<uuid:deal_id>", methods=["GET"])
@jwt_required()
def get_deal_by_id(deal_id):
    try:
        user_id = get_jwt_identity()

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

        logging.info(f"Fetching deal {deal_id} for user {user_id}")

        # Join through deal to verify the meeting belongs to this user's deals
        deal = (
            Deal.query
            .filter(Deal.id == deal_id)
            .first()
        )

        if not deal or not user_id:
            return jsonify({"error": "Deal not found or unauthorized"}), 404

        logging.info("Calculating number of pending actions")
        num_pending_actions = (
            db.session.query(func.count(Action.id))
            .join(Meeting, Action.meeting_id == Meeting.id)
            .join(Deal, Meeting.deal_id == Deal.id)
            .filter(Deal.id == deal.id)
            .filter(Action.status == ActionStatus.PENDING)
            .scalar()
        )
        last_contacted_on = (
            db.session.query(func.max(Meeting.start_time))
            .filter(Meeting.deal_id == deal.id)
            .scalar()
        )

        result = {
            "id": str(deal.id),
            "name": deal.name,
            "stage": deal.stage,
            "stage_signals": deal.stage_signals,
            "stage_reasoning": deal.stage_reasoning,
            "focus_areas": deal.focus_areas,
            "risks": deal.risks,
            "lead_qualification": deal.risks,
            "overview": deal.overview,
            "key_stakeholders": deal.key_stakeholders,
            "buyer_number": deal.buyer_number,
            "seller_number": deal.seller_number,
            "summary": deal.summary,
            "pain_points": deal.pain_points,
            "solutions": deal.solutions,
            "user_id": deal.user_id,
            "num_pending_actions": num_pending_actions,
            "last_contacted_on": last_contacted_on,
            "user_name": deal.user.name,
            "user_email": deal.user.email
        }

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Failed to fetch deal data: {e}")
        return jsonify({"error": f"Failed to fetch deal: {str(e)}"}), 500
