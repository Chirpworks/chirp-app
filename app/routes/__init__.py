from app.routes.google_auth import google_auth_bp


def register_routes(app):
    from .users import user_bp
    from .meetings import meetings_bp
    from .auth import auth_bp
    from .health import health_bp
    from .call_recordings import recording_bp
    from .tasks import task_bp
    from .agencies import agency_bp

    app.register_blueprint(user_bp, url_prefix="/api/user")
    app.register_blueprint(meetings_bp, url_prefix="/api/meetings")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(google_auth_bp, url_prefix="/api/google_auth")
    app.register_blueprint(health_bp, url_prefix="/api/health")
    app.register_blueprint(recording_bp, url_prefix='/api/call_recording')
    app.register_blueprint(task_bp, url_prefix='/api/task')
    app.register_blueprint(agency_bp, url_prefix='/api/agency')
