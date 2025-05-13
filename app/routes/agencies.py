import logging

from flask import Blueprint, jsonify, request

from app import Agency, db
from app.constants import AgencyName
from app.utils.auth_utils import add_agency_to_list

logging = logging.getLogger(__name__)

agency_bp = Blueprint("agency", __name__)


@agency_bp.route("/get_agency_names", methods=["GET"])
def get_agencies():
    agency_names = [agency.value for agency in AgencyName]
    return jsonify({"agencies": agency_names}), 200


@agency_bp.route("/create_agency", methods=["POST"])
def create_agency():
    try:
        logging.info("agency creation api initiated")
        data = request.get_json()

        name = data.get("name")

        logging.info(f"Creating Agency with id {id} and name {name}")

        new_agency = Agency(
            name=name
        )
        logging.info("Committing new agency to DB")
        db.session.add(new_agency)
        db.session.commit()

        add_agency_to_list(agency_id=new_agency.id, agency_name=name)
        logging.info(f"Created new agency successfully with name={name}")
        return jsonify({'message': 'Agency created successfully', 'agency_id': str(new_agency.id)}), 201
    except Exception as e:
        logging.error(f"Failed to create agency with error {e}")
        return jsonify({'error': 'Agency creation failed'}), 500
