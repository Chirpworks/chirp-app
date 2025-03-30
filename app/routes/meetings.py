from datetime import datetime
from typing import List, Union

from flask import Blueprint, request, jsonify

from app import User, Meeting, db, Job
from app.models.job import JobStatus
from app.models.meeting import MeetingStatus
from app.service.google_calendar.google_calendar_user import GoogleCalendarUserService

meetings_bp = Blueprint("meetings", __name__)


@meetings_bp.route('/get_next/<user_id>', methods=['GET'])
def get_upcoming_meetings(user_id) -> Union[List, dict]:
    try:
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
    try:
        data = request.get_json()
        title = data.get("title")
        scheduled_at = data.get("scheduled_at")
        user_id = data.get("user_id")

        if not title or not scheduled_at or not user_id:
            return jsonify({"error": "Missing required fields"}), 400

        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        new_meeting = Meeting(
            title=title,
            scheduled_at=datetime.fromisoformat(scheduled_at),
            user_id=user_id,
            status=MeetingStatus.SCHEDULED
        )
        db.session.add(new_meeting)
        db.session.commit()

        # Create corresponding job entry
        new_job = Job(
            meeting_id=new_meeting.id,  # Link job to the meeting
            status=JobStatus.INIT,  # Default status
            audio_s3_path=None  # Will be updated later
        )
        db.session.add(new_job)

        return jsonify({
            "id": new_meeting.id,
            "title": new_meeting.title,
            "scheduled_at": new_meeting.scheduled_at.isoformat(),
            "user_id": new_meeting.user_id,
            "status": new_meeting.status.value,
            "job_id": new_job.id
        }), 201
    except Exception as e:
        return jsonify({"error": f"Failed to create meeting. Error - {str(e)}"}), 500
