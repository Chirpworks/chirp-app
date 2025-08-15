import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.seller_service import SellerService
from app.search import SemanticSearchService, SemanticAnswerService


logging = logging.getLogger(__name__)

search_bp = Blueprint("search", __name__)


@search_bp.route("/", methods=["POST"])
@jwt_required()
def search():
    try:
        user_id = get_jwt_identity()
        user = SellerService.get_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        payload = request.get_json() or {}
        query = (payload.get("query") or "").strip()
        if not query:
            return jsonify({"results": []}), 200

        k = int(payload.get("k", 8))
        types = payload.get("types")
        # Optional seller filter when user chooses to scope further
        seller_id = payload.get("seller_id")

        svc = SemanticSearchService()
        results = svc.search(
            query=query,
            agency_id=str(user.agency_id),
            k=k,
            types=types,
            seller_id=seller_id,
        )
        return jsonify({"results": results}), 200
    except Exception as e:
        logging.error(f"Search failed: {e}")
        return jsonify({"error": "Search failed"}), 500

@search_bp.route("/answer", methods=["POST"])
@jwt_required()
def answer():
    try:
        user_id = get_jwt_identity()
        user = SellerService.get_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        payload = request.get_json() or {}
        query = (payload.get("query") or "").strip()
        if not query:
            return jsonify({"answer": "", "sources": []}), 200

        k = int(payload.get("k", 8))
        types = payload.get("types")
        seller_id = payload.get("seller_id")

        svc = SemanticAnswerService()
        result = svc.answer(
            query=query,
            agency_id=str(user.agency_id),
            k=k,
            types=types,
            seller_id=seller_id,
            model="gpt-4.1-mini",
        )
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Answer failed: {e}")
        return jsonify({"error": "Answer failed"}), 500


