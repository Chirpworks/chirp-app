import json
from datetime import timedelta
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app import db
from app.models.user import User
from app.models.jwt_token_blocklist import TokenBlocklist
from app.service.aws.s3_client import S3Client
from app.utils.auth_utils import generate_secure_otp, send_otp_email, generate_user_claims
from werkzeug.security import check_password_hash, generate_password_hash

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

        logging.info("Checking if User already exists")
        existing_user = User.query.filter((User.email == email) | (User.phone == phone)).first()
        if existing_user:
            logging.error({'error': 'User already exists'})
            return jsonify({'error': 'User already exists'}), 400
        logging.info(f"User doesn't exist. Creating new user with name {name} and email {email} and phone {phone}")

        logging.info(f"generating secure otp")
        otp = generate_secure_otp(length=16)

        logging.info(f"Creating user")
        new_user = User(email=email, password=otp, agency_id=agency_id, phone=phone, role=role, name=name)

        logging.info("Sending OTP via email")
        _ = send_otp_email(to_email=email, otp=otp)

        logging.info("Committing new user to DB")
        db.session.add(new_user)
        db.session.commit()

        logging.info(f"Created new user successfully with email={email}, name={name}")
        return jsonify({'message': 'User created successfully', 'name': name, 'user_id': str(new_user.id)}), 201
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

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            logging.error({'error': 'Invalid credentials'})
            return jsonify({'error': f'Invalid credentials for email: {email}'}), 401

        user_claims = generate_user_claims(user)
        access_token = user.generate_access_token(expires_delta=timedelta(minutes=15), additional_claims=user_claims)
        refresh_token = user.generate_refresh_token()
        return jsonify({'access_token': access_token, 'refresh_token': refresh_token, 'user_id': user.id}), 200
    except Exception as e:
        logging.error({'error': f"Failed to login with error with error: {e}"})
        return jsonify({'error': 'Login Failed'}), 500


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)  # Requires a valid refresh token
def refresh():
    user_id = get_jwt_identity()  # Get user ID from refresh token
    user = User.query.filter_by(id=user_id).first()
    user_claims = generate_user_claims(user)
    new_access_token = user.generate_access_token(expires_delta=timedelta(minutes=15), additional_claims=user_claims)
    refresh_token = user.generate_refresh_token()

    return jsonify({'access_token': new_access_token, 'refresh_token': refresh_token}), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]  # Get token's unique ID
    db.session.add(TokenBlocklist(jti=jti))  # Add to blacklist
    db.session.commit()

    return jsonify({"message": "Successfully logged out"}), 200


@auth_bp.route('/update_password', methods=['POST'])
def update_password():
    try:
        data = request.get_json()
        email = data.get('email') or ''
        old_password = data.get('old_password')
        new_password = data.get('new_password')

        user = User.query.filter_by(email=email).first()
        if not user:
            logging.error({"error": f"User not found with email {email}"})
            return jsonify({"message": "User not found"}), 404

        if not check_password_hash(user.password_hash, old_password):
            logging.error({"error": f"Old password incorrect for user with email {email}"})
            return jsonify({"message": "Old password incorrect"}), 401

        user.password_hash = generate_password_hash(new_password)
        db.session.commit()

        return jsonify({"message": "Password updated successfully"}), 200
    except Exception as e:
        logging.error(
            {"error": f"Failed to update password for user with email {email} with error {e}"}
        )
