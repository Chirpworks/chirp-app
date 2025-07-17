import logging
import traceback

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app import Agency, db
from app.constants import AgencyName
from app.utils.auth_utils import add_agency_to_list
from app.utils.call_recording_utils import normalize_phone_number
from app.services import AgencyService, ProductService, SellerService

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


@agency_bp.route("/sellers", methods=["GET"])
def get_agency_sellers():
    """
    Get all sellers/users for an agency.
    Accepts either agency_id or agency_name as query parameter.
    Returns all sellers for the specified agency.
    """
    try:
        logging.info("Agency sellers API initiated")
        
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
            logging.info(f"Fetching sellers for agency_id: {agency_id}")
            agency = AgencyService.get_by_id(agency_id)
            if not agency:
                return jsonify({'error': f'Agency with ID "{agency_id}" not found'}), 404
        else:
            logging.info(f"Fetching sellers for agency_name: {agency_name}")
            agency = AgencyService.get_by_field('name', agency_name)
            if not agency:
                return jsonify({'error': f'Agency with name "{agency_name}" not found'}), 404
        
        # Get sellers for the agency
        try:
            sellers = SellerService.get_by_agency(str(agency.id))
            
            # Format sellers for response
            seller_list = []
            for seller in sellers:
                seller_data = {
                    'id': str(seller.id),
                    'name': seller.name,
                    'email': seller.email,
                    'phone': seller.phone,
                    'role': seller.role.value,
                    'username': seller.username,
                    'manager_id': str(seller.manager_id) if seller.manager_id else None
                }
                seller_list.append(seller_data)
            
            logging.info(f"Retrieved {len(seller_list)} sellers for agency: {agency.name}")
            return jsonify({
                'agency_id': str(agency.id),
                'agency_name': agency.name,
                'sellers': seller_list,
                'total_count': len(seller_list)
            }), 200
            
        except SQLAlchemyError as e:
            logging.error(f"Database error while fetching sellers: {str(e)}")
            return jsonify({'error': 'Failed to fetch sellers due to database error'}), 500
            
    except Exception as e:
        logging.error(f"Failed to fetch agency sellers with error {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to fetch agency sellers'}), 500


@agency_bp.route("/details", methods=["GET"])
def get_agency_details():
    """
    Get detailed information for an agency.
    Accepts either agency_id or agency_name as query parameter.
    Returns comprehensive agency details including statistics.
    """
    try:
        logging.info("Agency details API initiated")
        
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
            logging.info(f"Fetching details for agency_id: {agency_id}")
            agency = AgencyService.get_by_id(agency_id)
            if not agency:
                return jsonify({'error': f'Agency with ID "{agency_id}" not found'}), 404
        else:
            logging.info(f"Fetching details for agency_name: {agency_name}")
            agency = AgencyService.get_by_field('name', agency_name)
            if not agency:
                return jsonify({'error': f'Agency with name "{agency_name}" not found'}), 404
        
        # Get basic agency details
        try:
            agency_details = {
                'id': str(agency.id),
                'name': agency.name,
                'description': agency.description
            }
            
            logging.info(f"Retrieved details for agency: {agency.name}")
            return jsonify(agency_details), 200
            
        except SQLAlchemyError as e:
            logging.error(f"Database error while fetching agency details: {str(e)}")
            return jsonify({'error': 'Failed to fetch agency details due to database error'}), 500
            
    except Exception as e:
        logging.error(f"Failed to fetch agency details with error {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to fetch agency details'}), 500


@agency_bp.route("/update_description", methods=["PUT"])
def update_agency_description():
    """
    Update the description for an agency.
    Accepts either agency_id or agency_name as query parameter and description in request body.
    """
    try:
        logging.info("Agency description update API initiated")
        
        # Get query parameters
        agency_id = request.args.get("agency_id")
        agency_name = request.args.get("agency_name")
        
        if not agency_id and not agency_name:
            return jsonify({'error': 'Either agency_id or agency_name is required'}), 400
        
        if agency_id and agency_name:
            return jsonify({'error': 'Provide either agency_id or agency_name, not both'}), 400
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        description = data.get("description")
        if description is None:
            return jsonify({'error': 'Description field is required'}), 400
        
        # Determine agency
        agency = None
        if agency_id:
            logging.info(f"Updating description for agency_id: {agency_id}")
            agency = AgencyService.get_by_id(agency_id)
            if not agency:
                return jsonify({'error': f'Agency with ID "{agency_id}" not found'}), 404
        else:
            logging.info(f"Updating description for agency_name: {agency_name}")
            agency = AgencyService.get_by_field('name', agency_name)
            if not agency:
                return jsonify({'error': f'Agency with name "{agency_name}" not found'}), 404
        
        # Update agency description
        try:
            updated_agency = AgencyService.update_agency_info(
                agency_id=str(agency.id), 
                description=description
            )
            
            if not updated_agency:
                return jsonify({'error': 'Failed to update agency description'}), 500
            
            logging.info(f"Updated description for agency: {agency.name}")
            return jsonify({
                'message': 'Agency description updated successfully',
                'agency_id': str(updated_agency.id),
                'agency_name': updated_agency.name,
                'description': updated_agency.description
            }), 200
            
        except SQLAlchemyError as e:
            logging.error(f"Database error while updating agency description: {str(e)}")
            return jsonify({'error': 'Failed to update agency description due to database error'}), 500
            
    except Exception as e:
        logging.error(f"Failed to update agency description with error {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to update agency description'}), 500


@agency_bp.route("/update_product/<uuid:product_id>", methods=["PUT"])
def update_product(product_id):
    """
    Update product details for a specific product.
    Accepts product_id in URL path and update data in request body.
    """
    try:
        logging.info(f"Product update API initiated for product_id: {product_id}")
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate that at least one field is provided
        allowed_fields = {'name', 'description', 'features'}
        provided_fields = set(data.keys())
        
        if not provided_fields:
            return jsonify({'error': 'At least one field (name, description, or features) must be provided'}), 400
        
        invalid_fields = provided_fields - allowed_fields
        if invalid_fields:
            return jsonify({'error': f'Invalid fields: {", ".join(invalid_fields)}. Allowed fields: {", ".join(allowed_fields)}'}), 400
        
        # Check if product exists
        product = ProductService.get_by_id(str(product_id))
        if not product:
            return jsonify({'error': f'Product with ID "{product_id}" not found'}), 404
        
        # Prepare update data
        update_data = {}
        if 'name' in data:
            name = data['name'].strip() if data['name'] else None
            if name is not None:
                update_data['name'] = name
        if 'description' in data:
            update_data['description'] = data['description']
        if 'features' in data:
            update_data['features'] = data['features']
        
        # Update product using ProductService
        try:
            updated_product = ProductService.update_product_info(
                product_id=str(product_id),
                **update_data
            )
            
            if not updated_product:
                return jsonify({'error': 'Failed to update product'}), 500
            
            logging.info(f"Updated product successfully: {product_id}")
            return jsonify({
                'message': 'Product updated successfully',
                'product_id': str(updated_product.id),
                'product_name': updated_product.name,
                'agency_id': str(updated_product.agency_id),
                'description': updated_product.description,
                'features': updated_product.features
            }), 200
            
        except SQLAlchemyError as e:
            logging.error(f"Database error while updating product: {str(e)}")
            return jsonify({'error': 'Failed to update product due to database error'}), 500
            
    except Exception as e:
        logging.error(f"Failed to update product {product_id} with error {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to update product'}), 500


@agency_bp.route("/add_seller", methods=["POST"])
def add_seller_to_agency():
    """
    Add a new seller to an agency.
    Accepts either agency_id or agency_name as query parameter and seller details in request body.
    """
    try:
        logging.info("Add seller to agency API initiated")
        
        # Get query parameters
        agency_id = request.args.get("agency_id")
        agency_name = request.args.get("agency_name")
        
        if not agency_id and not agency_name:
            return jsonify({'error': 'Either agency_id or agency_name is required'}), 400
        
        if agency_id and agency_name:
            return jsonify({'error': 'Provide either agency_id or agency_name, not both'}), 400
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Extract required fields
        email = data.get('email')
        phone = data.get('phone')
        name = data.get('name')
        password = data.get('password')
        
        # Validate required fields
        if not email or not phone or not name or not password:
            return jsonify({'error': 'Missing required fields: email, phone, name, and password are required'}), 400
        
        # Validate email format (basic validation)
        if '@' not in email or '.' not in email:
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Validate password strength (basic validation)
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400
        
        # Determine agency
        agency = None
        if agency_id:
            logging.info(f"Adding seller to agency_id: {agency_id}")
            agency = AgencyService.get_by_id(agency_id)
            if not agency:
                return jsonify({'error': f'Agency with ID "{agency_id}" not found'}), 404
        else:
            logging.info(f"Adding seller to agency_name: {agency_name}")
            agency = AgencyService.get_by_field('name', agency_name)
            if not agency:
                return jsonify({'error': f'Agency with name "{agency_name}" not found'}), 404
        
        # Check if seller already exists
        existing_user_by_email = SellerService.get_by_email(email)
        existing_user_by_phone = SellerService.get_by_phone(phone)
        if existing_user_by_email or existing_user_by_phone:
            return jsonify({'error': 'Seller with this email or phone already exists'}), 409
        
        # Normalize phone number
        normalized_phone = normalize_phone_number(phone)
        
        # Create seller using SellerService
        try:
            new_seller = SellerService.create_seller(
                email=email,
                password=password,
                agency_id=str(agency.id),
                phone=normalized_phone,
                role='user',  # Fixed role as 'Seller'
                name=name
            )
            
            logging.info(f"Created new seller successfully: {email} for agency: {agency.name}")
            return jsonify({
                'message': 'Seller added to agency successfully',
                'seller_id': str(new_seller.id),
                'seller_name': new_seller.name,
                'seller_email': new_seller.email,
                'seller_phone': new_seller.phone,
                'agency_id': str(agency.id),
                'agency_name': agency.name,
                'role': new_seller.role.value
            }), 201
            
        except SQLAlchemyError as e:
            logging.error(f"Database error while creating seller: {str(e)}")
            return jsonify({'error': 'Failed to create seller due to database error'}), 500
            
    except Exception as e:
        logging.error(f"Failed to add seller to agency with error {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to add seller to agency'}), 500
