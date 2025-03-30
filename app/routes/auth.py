from datetime import timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app import db
from app.constants import AGENCY_NAME_TO_AGENCY_ID_MAPPING
from app.models.user import User
from app.models.jwt_token_blocklist import TokenBlocklist

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    agency_name = data.get('agency_name')

    if not username or not email or not password or not agency_name:
        return jsonify({'error': 'Missing required fields'}), 400

    agency_id = AGENCY_NAME_TO_AGENCY_ID_MAPPING.get(agency_name)
    if not agency_id:
        return jsonify({'error': 'Invalid Agency Name'}), 400

    existing_user = User.query.filter((User.email == email) | (User.username == username)).first()
    if existing_user:
        return jsonify({'error': 'User already exists'}), 400

    new_user = User(username=username, email=email, password=password, agency_id=agency_id)

    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User created successfully', 'user_id': str(new_user.id)}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Missing email or password'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    access_token = user.generate_access_token()
    refresh_token = user.generate_refresh_token()
    return jsonify({'access_token': access_token, 'refresh_token': refresh_token, 'user_id': user.id}), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)  # Requires a valid refresh token
def refresh():
    user_id = get_jwt_identity()  # Get user ID from refresh token
    user = User.query.filter_by(id=user_id).first()
    new_access_token = user.generate_access_token(expires_delta=timedelta(minutes=15))

    return jsonify({'access_token': new_access_token}), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]  # Get token's unique ID
    db.session.add(TokenBlocklist(jti=jti))  # Add to blacklist
    db.session.commit()

    return jsonify({"message": "Successfully logged out"}), 200
