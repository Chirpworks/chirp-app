import json

from flask import Blueprint, redirect, request, session, jsonify
from flask_jwt_extended import get_current_user, jwt_required
from google_auth_oauthlib.flow import Flow
from app.config import Config

from app.external.google_calendar.google_calendar_user import GoogleCalendarUserService

google_auth_bp = Blueprint("google_auth", __name__)

REDIRECT_URI = "http://127.0.0.1:5000/auth/google/callback"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

flow = Flow.from_client_config(
    {
        "web": {
            "client_id": Config.GOOGLE_CLIENT_ID,
            "client_secret": Config.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=SCOPES,
    redirect_uri=REDIRECT_URI,
)


@google_auth_bp.route("/google_auth/login")
@jwt_required()
def google_login():
    """Redirect user to Google OAuth login."""
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    return redirect(auth_url)


@google_auth_bp.route("/google_auth/callback")
def google_callback():
    """Handle Google OAuth callback and store tokens in session securely."""
    flow.fetch_token(authorization_response=request.url)

    if not flow.credentials:
        return jsonify({"error": "Failed to retrieve credentials"}), 400

    session["google_credentials"] = json.loads(flow.credentials.to_json())

    return jsonify({"message": "Google connected successfully!"}), 200


@google_auth_bp.route("/google_auth/calendar")
@jwt_required()
def get_google_calendar():
    user = get_current_user()
    google_calendar_user_service = GoogleCalendarUserService()
    return google_calendar_user_service.get_google_calendar_events(user=user), 200


@google_auth_bp.route("/google_auth/logout")
@jwt_required()
def google_logout():
    """Clear Google credentials from session."""
    session.pop("google_credentials", None)
    return jsonify({"message": "Google disconnected successfully!"}), 200
