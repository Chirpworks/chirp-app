from flask import Blueprint, jsonify

user_bp = Blueprint("user", __name__)


@user_bp.route("/", methods=["GET"])
def get_users():
    return jsonify({"message": "List of users"})
