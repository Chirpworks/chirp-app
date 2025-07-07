import logging
import traceback

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app import Agency, db
from app.constants import AgencyName
from app.utils.auth_utils import add_agency_to_list
from app.services import AgencyService, ProductService

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


@agency_bp.route("/create_product", methods=["POST"])
def create_product():
    """
    Create a new product for an agency.
    Accepts agency name and product details as JSON data.
    """
    try:
        logging.info("Product creation API initiated")
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Extract required fields
        agency_name = data.get("agency_name")
        product_name = data.get("name")
        
        if not agency_name:
            return jsonify({'error': 'Agency name is required'}), 400
            
        if not product_name:
            return jsonify({'error': 'Product name is required'}), 400

        # Trim whitespace and validate names
        agency_name = agency_name.strip()
        product_name = product_name.strip()
        
        if not agency_name:
            return jsonify({'error': 'Agency name cannot be empty'}), 400
            
        if not product_name:
            return jsonify({'error': 'Product name cannot be empty'}), 400

        logging.info(f"Creating product '{product_name}' for agency '{agency_name}'")

        # Get agency by name
        agency = AgencyService.get_by_field('name', agency_name)
        if not agency:
            return jsonify({'error': f'Agency with name "{agency_name}" not found'}), 404

        # Extract optional product fields
        description = data.get("description")
        features = data.get("features")

        # Create product using ProductService
        try:
            new_product = ProductService.create_product(
                name=product_name,
                agency_id=str(agency.id),
                description=description,
                features=features
            )
            
            logging.info(f"Created new product successfully: {product_name} for agency: {agency_name}")
            return jsonify({
                'message': 'Product created successfully',
                'product_id': str(new_product.id),
                'product_name': new_product.name,
                'agency_id': str(agency.id),
                'agency_name': agency.name,
                'description': new_product.description,
                'features': new_product.features
            }), 201
            
        except SQLAlchemyError as e:
            logging.error(f"Database error while creating product: {str(e)}")
            return jsonify({'error': 'Failed to create product due to database error'}), 500
            
    except Exception as e:
        logging.error(f"Failed to create product with error {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Product creation failed'}), 500


@agency_bp.route("/product_catalogue", methods=["GET"])
def get_agency_product_catalogue():
    """
    Get product catalogue for an agency.
    Accepts either agency_id or agency_name as query parameter.
    Returns all products for the specified agency.
    """
    try:
        logging.info("Product catalogue API initiated")
        
        # Get query parameters
        agency_id = request.args.get("agency_id")
        agency_name = request.args.get("agency_name")
        
        if not agency_id and not agency_name:
            return jsonify({'error': 'Either agency_id or agency_name is required'}), 400
        
        if agency_id and agency_name:
            return jsonify({'error': 'Provide either agency_id or agency_name, not both'}), 400
        
        # Determine agency
        agency = None
        if agency_id:
            logging.info(f"Fetching product catalogue for agency_id: {agency_id}")
            agency = AgencyService.get_by_id(agency_id)
            if not agency:
                return jsonify({'error': f'Agency with ID "{agency_id}" not found'}), 404
        else:
            logging.info(f"Fetching product catalogue for agency_name: {agency_name}")
            agency = AgencyService.get_by_field('name', agency_name)
            if not agency:
                return jsonify({'error': f'Agency with name "{agency_name}" not found'}), 404
        
        # Get products for the agency
        try:
            products = ProductService.get_products_by_agency(str(agency.id))
            
            # Format products for response
            product_list = []
            for product in products:
                product_data = {
                    'id': str(product.id),
                    'name': product.name,
                    'description': product.description,
                    'features': product.features
                }
                product_list.append(product_data)
            
            logging.info(f"Retrieved {len(product_list)} products for agency: {agency.name}")
            return jsonify({
                'agency_id': str(agency.id),
                'agency_name': agency.name,
                'products': product_list,
                'total_count': len(product_list)
            }), 200
            
        except SQLAlchemyError as e:
            logging.error(f"Database error while fetching products: {str(e)}")
            return jsonify({'error': 'Failed to fetch products due to database error'}), 500
            
    except Exception as e:
        logging.error(f"Failed to fetch product catalogue with error {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to fetch product catalogue'}), 500
