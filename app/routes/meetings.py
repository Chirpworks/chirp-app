import traceback
from datetime import datetime, timedelta
from typing import List, Union
from zoneinfo import ZoneInfo

import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import and_

from app import Seller, Meeting, db, Job
from app.constants import MeetingSource, CallDirection
from app.models import meeting
from app.models.job import JobStatus
from app.models.mobile_app_calls import MobileAppCall
from app.models.seller import SellerRole
from app.service.google_calendar.google_calendar_user import GoogleCalendarUserService
from app.utils.call_recording_utils import denormalize_phone_number
from app.utils.utils import human_readable_duration
from app.services import MeetingService, SellerService

meetings_bp = Blueprint("meetings", __name__)

logging = logging.getLogger(__name__)


@meetings_bp.route('/get_next/<user_id>', methods=['GET'])
def get_upcoming_meetings(user_id) -> Union[List, dict]:
    try:
        pass
        # TODO: fetch data from cache if exists. refresh from google calendar and store new data in db as well.
        # TODO: Save new meetings in DB
        # TODO: submit job to scheduler
        num_events = request.args.get('num_events')
        google_calendar_caller = GoogleCalendarUserService()
        # events = google_calendar_caller.fetch_google_calendar_events(num_events)
        # schedule_jobs(events)
        return []
    except Exception as e:
        return {"error": f"failed to create account. Error - {e}"}


@meetings_bp.route('/create', methods=['POST'])
def create_meeting():
    pass
    # try:
    #     data = request.get_json()
    #     title = data.get("title")
    #     scheduled_at = data.get("scheduled_at")
    #     user_id = data.get("user_id")
    #
    #     if not title or not scheduled_at or not user_id:
    #         return jsonify({"error": "Missing required fields"}), 400
    #
    #     user = Seller.query.get(user_id)
    #     if not user:
    #         return jsonify({"error": "Seller not found"}), 404
    #
    #     new_meeting = Meeting(
    #         title=title,
    #         scheduled_at=datetime.fromisoformat(scheduled_at),
    #         user_id=user_id,
    #         status=MeetingStatus.SCHEDULED
    #     )
    #     db.session.add(new_meeting)
    #     db.session.commit()
    #
    #     # Create corresponding job entry
    #     new_job = Job(
    #         meeting_id=new_meeting.id,  # Link job to the meeting
    #         status=JobStatus.INIT,  # Default status
    #         audio_s3_path=None  # Will be updated later
    #     )
    #     db.session.add(new_job)
    #
    #     return jsonify({
    #         "id": new_meeting.id,
    #         "title": new_meeting.title,
    #         "scheduled_at": new_meeting.scheduled_at.isoformat(),
    #         "user_id": new_meeting.user_id,
    #         "status": new_meeting.status.value,
    #         "job_id": new_job.id
    #     }), 201
    # except Exception as e:
    #     return jsonify({"error": f"Failed to create meeting. Error - {str(e)}"}), 500


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
        user_ids = team_member_ids if team_member_ids else [user_id]
        call_history = MeetingService.get_call_history(user_ids)
        
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
        meeting_data = MeetingService.get_meeting_with_job(meeting_id, user_id)
        if not meeting_data:
            return jsonify({"error": "Meeting not found or unauthorized"}), 404

        return jsonify(meeting_data), 200

    except Exception as e:
        logging.error(f"Failed to fetch call data: {e}")
        return jsonify({"error": f"Failed to fetch meeting: {str(e)}"}), 500


@meetings_bp.route("/call_diarization/<uuid:meeting_id>", methods=["GET"])
@jwt_required()
def get_meeting_diarization_by_id(meeting_id):
    try:
        user_id = get_jwt_identity()

        team_member_id = request.args.get("team_member_id")
        if team_member_id:
            user = Seller.query.filter_by(id=user_id).first()
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

        logging.info(f"Fetching diarization for meeting_id {meeting_id} for user {user_id}")

        # Verify the meeting belongs to this user
        meeting = (
            Meeting.query
            .join(Meeting.seller)
            .filter(Meeting.id == meeting_id, Seller.id == user_id)
            .first()
        )

        if not meeting:
            return jsonify({"error": "Meeting not found or unauthorized"}), 404

        result = {
            "id": str(meeting.id),
            "diarization": meeting.diarization,
        }

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Failed to fetch meeting diarization data: {e}")
        return jsonify({"error": f"Failed to fetch meeting: {str(e)}"}), 500


@meetings_bp.route("/call_data/feedback/<uuid:meeting_id>", methods=["GET"])
@jwt_required()
def get_meeting_feedback_by_id(meeting_id):
    try:
        user_id = get_jwt_identity()

        # Verify the meeting belongs to this user
        meeting = (
            Meeting.query
            .join(Meeting.seller)
            .filter(Meeting.id == meeting_id, Seller.id == user_id)
            .first()
        )

        if not meeting:
            return jsonify({"error": "Meeting not found or unauthorized"}), 404

        result = {
            "id": str(meeting.id),
            "feedback": meeting.feedback
        }

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": f"Failed to fetch meeting: {str(e)}"}), 500


@meetings_bp.route("/last_synced_call", methods=["GET"])
def get_last_synced_call_id():
    try:
        seller_number = request.args.get("sellerNumber")
        logging.info(f"getting last synced call id for phone: {seller_number}")

        user = Seller.query.filter_by(phone=seller_number).first()
        if not user:
            logging.info(f"user not found for phone {seller_number}")
            return jsonify({"message": f"No user with phone number {seller_number} found"}), 404

        last_app_call = (
            MobileAppCall.query
            .filter(MobileAppCall.seller_number == seller_number)
            .order_by(MobileAppCall.start_time.desc())
            .first()
        )

        last_meeting = (
            Meeting.query
            .filter(Meeting.seller_number == seller_number)
            .order_by(Meeting.start_time.desc())
            .first()
        )

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
        return jsonify({"error": f"Failed to fetch last synced call id: {str(e)}"}), 500
