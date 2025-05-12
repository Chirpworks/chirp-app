import logging
import sys

from flask_session import Session
from flask_cors import CORS

from app.extensions import migrate, db, jwt
from app.config import Config

from app.models.agency import Agency
from app.models.user import User
from app.models.job import Job
from app.models.meeting import Meeting
from app.models.deal import Deal
from app.models.action import Action
from app.models.exotel_calls import ExotelCall
from app.models.mobile_app_calls import MobileAppCall
from app.models.jwt_token_blocklist import TokenBlocklist
from app.service.aws.ecs_client import ECSClient

from flask import Flask

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.info("Logging is set up and initialized.")


def allow_localhost_origin(origin):
    return origin and origin.startswith("http://localhost")

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    return db.session.query(TokenBlocklist.id).filter_by(jti=jti).first() is not None


def create_app():
    app = Flask(__name__)
    CORS(app, supports_credentials=True, origins=["http://localhost:8080", "http://app.chirpworks.ai", "https://app.chirpworks.ai"])
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

    with app.app_context():
        from app.routes import register_routes
        register_routes(app)

        # ecs_client = ECSClient()

        # Start job monitoring in a separate thread
        # monitor_thread = threading.Thread(target=ecs_client.monitor_agent_jobs, args=(app,), daemon=True)
        # monitor_thread.start()

    # Set up token revocation checking
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked_callback(jwt_header, jwt_payload):
        return check_if_token_revoked(jwt_header, jwt_payload)

    return app
