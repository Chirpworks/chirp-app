from functools import wraps
from flask_jwt_extended import get_jwt
from flask import jsonify


def role_required(required_role):
    """Decorator to restrict access based on user role"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            if claims.get("role") != required_role:
                return jsonify({"message": "Access denied: Insufficient permissions"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
