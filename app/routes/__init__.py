from app.routes.google_auth import google_auth_bp


def register_routes(app):
    from .users import user_bp
    from .meetings import meetings_bp
    from .auth import auth_bp
    from .health import health_bp
    from .call_records import call_record_bp
    from .agencies import agency_bp
    from .actions import action_bp
    from .analysis import analysis_bp
    from .deals import deals_bp

    app.register_blueprint(user_bp, url_prefix="/api/user")
    app.register_blueprint(meetings_bp, url_prefix="/api/meetings")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(google_auth_bp, url_prefix="/api/google_auth")
    app.register_blueprint(health_bp, url_prefix="/api/health")
    app.register_blueprint(call_record_bp, url_prefix='/api/call_records')
    app.register_blueprint(agency_bp, url_prefix='/api/agency')
    app.register_blueprint(action_bp, url_prefix='/api/actions')
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')
    app.register_blueprint(deals_bp, url_prefix='/api/deals')
