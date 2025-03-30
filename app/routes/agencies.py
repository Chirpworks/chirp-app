from flask import Blueprint, jsonify

from app.constants import AgencyName

agency_bp = Blueprint("agency", __name__)


@agency_bp.route("/get_agency_names", methods=["GET"])
def get_agencies():
    agency_names = [agency.value for agency in AgencyName]
    return jsonify({"agencies": agency_names}), 200
