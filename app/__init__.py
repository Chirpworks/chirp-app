import os
import threading

from celery import Celery
from flask import Flask
from flask_session import Session

from app.extensions import migrate, db, jwt
from app.config import Config

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from app.models.agency import Agency
from app.models.user import User
from app.models.job import Job
from app.models.meeting import Meeting
from app.models.jwt_token_blocklist import TokenBlocklist
from app.service.aws.ecs_client import ECSClient

from flask import Flask

# Initialize APScheduler with Flask
jobstore = {
    "default": SQLAlchemyJobStore(url="sqlite:///jobs.db")  # Use SQLite for simplicity
}
scheduler = BackgroundScheduler(jobstores=jobstore)
celery = Celery(__name__, broker=Config.CELERY_BROKER_URL)


@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    return db.session.query(TokenBlocklist.id).filter_by(jti=jti).first() is not None


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY
    app.config.update(
        CELERY_BROKER_URL="sqs://",
        CELERY_RESULT_BACKEND="db+sqlite:///results.sqlite",
    )
    Session(app)
    db.init_app(app)
    migrate.init_app(app, db)

    jwt.init_app(app)

    global celery
    celery = make_celery(celery, app)

    with app.app_context():
        from app.routes import register_routes
        register_routes(app)
        scheduler.start()

        # ecs_client = ECSClient()

        # Start job monitoring in a separate thread
        # monitor_thread = threading.Thread(target=ecs_client.monitor_agent_jobs, args=(app,), daemon=True)
        # monitor_thread.start()

    # Set up token revocation checking
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked_callback(jwt_header, jwt_payload):
        return check_if_token_revoked(jwt_header, jwt_payload)

    return app


def make_celery(celery, app):
    celery.conf.update(app.config)
    celery.conf.update(
        broker_transport_options={
            "region": "ap-south-1",
            "visibility_timeout": 300,  # Avoid task duplication issues
            "wait_time_seconds": 20  # Long polling (max 20s)
        }
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
