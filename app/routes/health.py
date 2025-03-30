from flask import Blueprint

health_bp = Blueprint('health', __name__)

@health_bp.route('/hello', methods=['GET'])
def hello_world():
    return {"message": "Hello, World!"}, 200
