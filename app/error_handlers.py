# app/error_handlers.py
from flask import jsonify


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({"error": "Not Found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal Server Error"}), 500

    app.register_error_handler(404, not_found_error)
    app.register_error_handler(500, internal_error)
