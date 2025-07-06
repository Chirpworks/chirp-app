import logging
import traceback

from flask import Blueprint, jsonify, request

from app import Agency, db
from app.constants import AgencyName
from app.utils.auth_utils import add_agency_to_list
from app.services import AgencyService

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

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        name = data.get("name")
        
        if not name:
            return jsonify({'error': 'Agency name is required'}), 400

        # Trim whitespace and validate name
        name = name.strip()
        if not name:
            return jsonify({'error': 'Agency name cannot be empty'}), 400

        logging.info(f"Creating Agency with name: {name}")

        # Use AgencyService for creation with built-in validation
        try:
            new_agency = AgencyService.create_agency(name=name)
            
            # Add to S3 mapping only if database creation succeeds
            add_agency_to_list(agency_id=str(new_agency.id), agency_name=name)
            
            logging.info(f"Created new agency successfully with name={name}")
            return jsonify({
                'message': 'Agency created successfully', 
                'agency_id': str(new_agency.id),
                'agency_name': new_agency.name
            }), 201
            
        except ValueError as ve:
            # Handle duplicate name error from service
            logging.warning(f"Agency creation failed - duplicate name: {str(ve)}")
            return jsonify({'error': str(ve)}), 409  # Conflict status code
            
    except Exception as e:
        logging.error(f"Failed to create agency with error {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Agency creation failed'}), 500
