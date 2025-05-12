import json
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import func

from app import Meeting, db
from app.models.action import Action, ActionStatus
from app.models.deal import Deal

logging = logging.getLogger(__name__)

deals_bp = Blueprint("deal", __name__)


@deals_bp.route("/get_deals", methods=["GET"])
@jwt_required()
def get_deals():
    try:
        user_id = get_jwt_identity()

        # Parse optional query params
        deal_id = request.args.get("deal_id")

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
                "last_contacted_on": last_contacted_on
            })

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": f"Failed to fetch actions: {str(e)}"}), 500


@deals_bp.route("/deal_details/<uuid:deal_id>", methods=["GET"])
@jwt_required()
def get_deal_by_id(deal_id):
    try:
        user_id = get_jwt_identity()

        # Join through deal to verify the meeting belongs to this user's deals
        deal = (
            Deal.query
            .filter(Deal.id == deal_id)
            .first()
        )

        num_pending_actions = (
            db.session.query(func.count(Action.id))
            .join(Meeting, Action.meeting_id == Meeting.id)
            .join(Deal, Meeting.deal_id == Deal.id)
            .filter(Deal.id == deal.id)
            .filter(Action.status == ActionStatus.PENDING)
            .scalar()
        )

        if not deal or not user_id:
            return jsonify({"error": "Deal not found or unauthorized"}), 404

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
            "num_pending_actions": num_pending_actions
        }

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Failed to fetch deal data: {e}")
        return jsonify({"error": f"Failed to fetch deal: {str(e)}"}), 500
