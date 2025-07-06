import traceback
from typing import Union

import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.services import SellerService, MeetingService, CallService
from app.models.seller import SellerRole
from app.external.google_calendar.google_calendar_user import GoogleCalendarUserService

meetings_bp = Blueprint("meetings", __name__)

logging = logging.getLogger(__name__)


@meetings_bp.route('/get_next/<user_id>', methods=['GET'])
def get_upcoming_meetings(user_id):
    try:
        # TODO: fetch data from cache if exists. refresh from google calendar and store new data in db as well.
        # TODO: Save new meetings in DB
        # TODO: submit job to scheduler
        num_events = request.args.get('num_events')
        google_calendar_caller = GoogleCalendarUserService()
        # events = google_calendar_caller.fetch_google_calendar_events(num_events)
        # schedule_jobs(events)
        return jsonify([])
    except Exception as e:
        logging.error(f"Failed to get upcoming meetings: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"failed to create account. Error - {e}"})


@meetings_bp.route('/create', methods=['POST'])
def create_meeting():
    return jsonify({"error": "Not implemented"}), 501


@meetings_bp.route("/call_history", methods=["GET"])
@jwt_required()
def get_meeting_history():
    try:
        user_id = get_jwt_identity()

        team_member_ids = request.args.getlist("team_member_id")
        if team_member_ids:
            user = SellerService.get_by_id(user_id)
            if not user:
                logging.error("User not found; unauthorized")
                return jsonify({"error": "User not found or unauthorized"}), 404
            if user.role != SellerRole.MANAGER:
                logging.info(f"Unauthorized User. 'team_member_id' query parameter is only applicable for a manager.")
                return jsonify(
                    {"error": "Unauthorized User: 'team_member_id' query parameter is only applicable for a manager"}
                )

            # Validate team member IDs
            for member_id in team_member_ids:
                member = SellerService.get_by_id(member_id)
                if not member:
                    logging.error(f"Seller with id {member_id} not found; unauthorized")
                    return jsonify({"error": "Seller not found or unauthorized"}), 404
            logging.info(f"Fetching call history for users {team_member_ids}")

        # Use MeetingService to get call history
        call_history = MeetingService.get_call_history(user_id, team_member_ids)
        
        return jsonify(call_history), 200

    except Exception as e:
        logging.error("Failed to fetch call history: %s", traceback.format_exc())
        return jsonify({"error": f"Failed to fetch call history: {str(e)}"}), 500


@meetings_bp.route("/call_data/<uuid:meeting_id>", methods=["GET"])
@jwt_required()
def get_meeting_by_id(meeting_id):
    try:
        user_id = get_jwt_identity()

        team_member_id = request.args.get("team_member_id")
        if team_member_id:
            user = SellerService.get_by_id(user_id)
            if not user:
                logging.error("Seller not found; unauthorized")
                return jsonify({"error": "Seller not found or unauthorized"}), 404
            if user.role != SellerRole.MANAGER:
                logging.info(f"Unauthorized Seller. 'team_member_id' query parameter is only applicable for a manager.")
                return jsonify(
                    {"error": "Unauthorized Seller: 'team_member_id' query parameter is only applicable for a manager"}
                )
            logging.info(f"setting user_id to {team_member_id=} for manager_id={user_id}")
            user_id = team_member_id

        logging.info(f"Fetching call_data for meeting_id {meeting_id} for user {user_id}")

        # Use MeetingService to get meeting with job details
        meeting_data = MeetingService.get_meeting_with_job(meeting_id)
        if not meeting_data:
            return jsonify({"error": "Meeting not found"}), 404
            
        # Verify user has access to this meeting
        if str(meeting_data.seller_id) != user_id:
            return jsonify({"error": "Meeting not found or unauthorized"}), 404

        return jsonify(meeting_data), 200

    except Exception as e:
        logging.error(f"Failed to fetch call data: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch meeting: {str(e)}"}), 500


@meetings_bp.route("/call_data/feedback/<uuid:meeting_id>", methods=["GET"])
@jwt_required()
def get_meeting_feedback_by_id(meeting_id):
    try:
        user_id = get_jwt_identity()

        # Verify the meeting belongs to this user
        meeting = MeetingService.get_by_id(meeting_id)
        if not meeting or str(meeting.seller_id) != user_id:
            return jsonify({"error": "Meeting not found or unauthorized"}), 404

        result = {
            "id": str(meeting.id),
            "feedback": meeting.feedback
        }

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Failed to fetch meeting feedback: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch meeting: {str(e)}"}), 500


@meetings_bp.route("/call_data/transcription/<uuid:meeting_id>", methods=["GET"])
@jwt_required()
def get_meeting_transcription_by_id(meeting_id):
    try:
        logging.info(f"Fetching transcription for meeting_id {meeting_id}")

        # Verify the meeting belongs to this user
        meeting = MeetingService.get_by_id(meeting_id)
        if not meeting:
            return jsonify({"error": "Meeting not found or unauthorized"}), 404

        result = {
            "id": str(meeting.id),
            "transcription": meeting.transcription
        }

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Failed to fetch meeting transcription data: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch meeting transcription: {str(e)}"}), 500


@meetings_bp.route("/last_synced_call", methods=["GET"])
def get_last_synced_call_id():
    try:
        seller_number = request.args.get("sellerNumber")
        if not seller_number:
            return jsonify({"error": "Missing sellerNumber parameter"}), 400
            
        logging.info(f"getting last synced call id for phone: {seller_number}")

        user = SellerService.get_by_phone(seller_number)
        if not user:
            logging.info(f"user not found for phone {seller_number}")
            return jsonify({"message": f"No user with phone number {seller_number} found"}), 404

        last_app_call = CallService.get_last_mobile_app_call_by_seller(seller_number)

        last_meeting = MeetingService.get_last_meeting_by_seller(user.id)

        if last_app_call and not last_meeting:
            logging.info(f"last synced call id returned: {last_app_call.mobile_app_call_id}")
            return jsonify(
                {"source": "mobile_app_call", "last_synced_call_id": str(last_app_call.mobile_app_call_id)}
            ), 200
        elif last_meeting and not last_app_call:
            logging.info(f"last synced call id returned: {last_meeting.mobile_app_call_id}")
            return jsonify({"source": "meeting", "last_synced_call_id": str(last_meeting.mobile_app_call_id)}), 200
        elif last_app_call and last_meeting:
            if last_app_call.start_time > last_meeting.start_time:
                logging.info(f"last synced call id returned: {last_app_call.mobile_app_call_id}")
                return jsonify(
                    {"source": "mobile_app_call", "last_synced_call_id": str(last_app_call.mobile_app_call_id)}
                ), 200
            else:
                logging.info(f"last synced call id returned: {last_meeting.mobile_app_call_id}")
                return jsonify({"source": "meeting", "last_synced_call_id": str(last_meeting.mobile_app_call_id)}), 200
        else:
            logging.info("No synced calls found")
            return jsonify({"message": "No synced calls found", "last_synced_call_id": None}), 200

    except Exception as e:
        logging.error(f"Failed to fetch last synced call id: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch last synced call id: {str(e)}"}), 500


@meetings_bp.route("/call_data/summary/<uuid:meeting_id>", methods=["PUT"])
def update_meeting_summary(meeting_id):
    """
    Update call summary for a specific meeting.
    Updates the summary field in the Meetings table.
    """
    try:
        logging.info(f"Updating call summary for meeting_id {meeting_id}")

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        call_summary = data.get("callSummary")
        if call_summary is None:
            return jsonify({"error": "callSummary field is required"}), 400

        # Verify the meeting exists
        meeting = MeetingService.get_by_id(meeting_id)
        if not meeting:
            return jsonify({"error": "Meeting not found"}), 404

        # Update the meeting summary using MeetingService
        updated_meeting = MeetingService.update_llm_analysis(meeting_id, {"summary": call_summary})
        if not updated_meeting:
            return jsonify({"error": "Failed to update meeting summary"}), 500

        result = {
            "id": str(updated_meeting.id),
            "summary": updated_meeting.summary
        }

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Failed to update meeting summary for meeting_id {meeting_id}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to update meeting summary: {str(e)}"}), 500
