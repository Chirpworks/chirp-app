import json
from datetime import timedelta
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app import db
from app.models.seller import Seller
from app.models.jwt_token_blocklist import TokenBlocklist
from app.service.aws.s3_client import S3Client
from app.utils.auth_utils import generate_secure_otp, send_otp_email, generate_user_claims
from werkzeug.security import check_password_hash, generate_password_hash

from app.utils.call_recording_utils import normalize_phone_number
from app.services import AuthService, SellerService, TokenBlocklistService

logging = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


def load_agency_mapping_from_s3():
    try:
        s3_client = S3Client()
        content = s3_client.get_file_content(bucket_name="agency-name-mapping-config", key="agency_mapping.json")
        return json.loads(content)
    except Exception as e:
        print(f"Failed to fetch agency mapping from S3: {e}")
        return {}


@auth_bp.route('/signup', methods=['POST'])
def signup():
    try:
        logging.info("signup flow initiated")
        data = request.get_json()
        email = data.get('email')
        agency_name = data.get('agency_name')
        phone = data.get('phone')
        role = data.get('role')
        name = data.get('name')

        logging.info(f"Data received for signup: {email=}, {agency_name=}, {phone=}, {name=}")

        if not name or not email or not agency_name or not phone:
            logging.error({'error': 'Missing required fields'})
            return jsonify({'error': 'Missing required fields'}), 400

        agency_id_name_mapping = load_agency_mapping_from_s3()
        agency_id = agency_id_name_mapping.get(agency_name)
        if not agency_id:
            logging.error({'error': 'Invalid Agency Name'})
            return jsonify({'error': 'Invalid Agency Name'}), 400

        logging.info("Checking if Seller already exists")
        existing_user_by_email = SellerService.get_by_email(email)
        existing_user_by_phone = SellerService.get_by_phone(phone)
        if existing_user_by_email or existing_user_by_phone:
            logging.error({'error': 'Seller already exists'})
            return jsonify({'error': 'Seller already exists'}), 400
        logging.info(f"Seller doesn't exist. Creating new user with name {name} and email {email} and phone {phone}")

        logging.info(f"generating secure otp")
        otp = generate_secure_otp(length=16)

        logging.info(f"normalizing phone number")
        phone = normalize_phone_number(phone)

        logging.info("Sending OTP via email")
        _ = send_otp_email(to_email=email, otp=otp)

        logging.info(f"Creating user using SellerService")
        new_user = SellerService.create_seller(
            email=email, 
            password=otp, 
            agency_id=agency_id, 
            phone=phone, 
            role=role, 
            name=name
        )

        logging.info(f"Created new user successfully with email={email}, name={name}")
        return jsonify({'message': 'Seller created successfully', 'name': name, 'user_id': str(new_user.id)}), 201
    except Exception as e:
        logging.error(f"Failed to complete signup with error {e}")
        return jsonify({'error': 'Signup Failed'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        logging.info("Logging in")
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            logging.error({'error': 'Missing email or password'})
            return jsonify({'error': 'Missing email or password'}), 400

        # Use AuthService for authentication
        auth_result = AuthService.authenticate_user(email, password)
        if not auth_result:
            logging.error({'error': 'Invalid credentials'})
            return jsonify({'error': f'Invalid credentials for email: {email}'}), 401

        return jsonify({
            'access_token': auth_result['tokens']['access_token'], 
            'refresh_token': auth_result['tokens']['refresh_token'], 
            'user_id': auth_result['user']['id']
        }), 200
        
    except Exception as e:
        logging.error({'error': f"Failed to login with error: {e}"})
        return jsonify({'error': 'Login Failed'}), 500


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)  # Requires a valid refresh token
def refresh():
    try:
        user_id = get_jwt_identity()  # Get user ID from refresh token
        
        # Use AuthService for token refresh
        tokens = AuthService.refresh_user_tokens(user_id)
        if not tokens:
            return jsonify({'error': 'Failed to refresh tokens'}), 401

        return jsonify({
            'access_token': tokens['access_token'], 
            'refresh_token': tokens['refresh_token']
        }), 200
        
    except Exception as e:
        logging.error(f"Token refresh error: {str(e)}")
        return jsonify({'error': 'Token refresh failed'}), 500


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    try:
        # Use AuthService for logout
        success = AuthService.logout_user()
        if not success:
            return jsonify({"error": "Logout failed"}), 500

        return jsonify({"message": "Successfully logged out"}), 200
        
    except Exception as e:
        logging.error(f"Logout error: {str(e)}")
        return jsonify({"error": "Logout failed"}), 500


@auth_bp.route('/update_password', methods=['POST'])
def update_password():
    try:
        data = request.get_json()
        email = data.get('email') or ''
        old_password = data.get('old_password')
        new_password = data.get('new_password')

        if not email or not old_password or not new_password:
            return jsonify({"error": "Missing required fields"}), 400

        # Get user by email
        user = SellerService.get_by_email(email)
        if not user:
            logging.error({"error": f"Seller not found with email {email}"})
            return jsonify({"message": "Seller not found"}), 404

        # Use AuthService for password change
        success = AuthService.change_user_password(str(user.id), old_password, new_password)
        if not success:
            return jsonify({"message": "Old password incorrect"}), 401

        return jsonify({"message": "Password updated successfully"}), 200
        
    except Exception as e:
        logging.error(f"Failed to update password for user with email {email}: {str(e)}")
        return jsonify({"error": "Password update failed"}), 500
