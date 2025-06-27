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
from app.models.deal import Deal
from app.models.job import JobStatus
from app.models.mobile_app_calls import MobileAppCall
from app.models.seller import SellerRole
from app.service.google_calendar.google_calendar_user import GoogleCalendarUserService
from app.utils.call_recording_utils import denormalize_phone_number
from app.utils.utils import human_readable_duration

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

        deal_id = request.args.get("dealId")
        team_member_ids = request.args.getlist("team_member_id")
        if team_member_ids:
            user = Seller.query.filter_by(id=user_id).first()
            if not user:
                logging.error("User not found; unauthorized")
                return jsonify({"error": "User not found or unauthorized"}), 404
            if user.role != SellerRole.MANAGER:
                logging.info(f"Unauthorized User. 'team_member_id' query parameter is only applicable for a manager.")
                return jsonify(
                    {"error": "Unauthorized User: 'team_member_id' query parameter is only applicable for a manager"}
                )

        if team_member_ids:
            for user_id in team_member_ids:
                user = Seller.query.filter_by(id=user_id).first()
                if not user:
                    logging.error(f"Seller with id {user_id} not found; unauthorized")
                    return jsonify({"error": "Seller not found or unauthorized"}), 404
            logging.info(f"Fetching actions data for users {team_member_ids}")

            logging.info(f"Fetching call history for users {team_member_ids}")
            # Join through deals to fetch user's meetings
            meetings_query = (
                Meeting.query
                .join(Meeting.deal)
                .filter(Deal.user_id.in_(team_member_ids))
                .order_by(Meeting.start_time.desc())
            )
            mobile_app_calls_query = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id.in_(team_member_ids))
                .order_by(MobileAppCall.start_time.desc())
            )
        else:
            # Join through deals to fetch user's meetings
            meetings_query = (
                Meeting.query
                .join(Meeting.deal)
                .filter(Deal.user_id == user_id)
                .order_by(Meeting.start_time.desc())
            )
            mobile_app_calls_query = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id == user_id)
                .order_by(MobileAppCall.start_time.desc())
            )

        if deal_id:
            meetings_query = meetings_query.filter(Meeting.deal_id == deal_id)
            deal = Deal.query.get(deal_id)
            mobile_app_calls_query = mobile_app_calls_query.filter(
                and_(
                    MobileAppCall.buyer_number == deal.buyer_number,
                    MobileAppCall.seller_number == deal.seller_number,
                ))

        meetings = meetings_query.all()
        mobile_app_calls = mobile_app_calls_query.all()
        meetings.extend(mobile_app_calls)
        meetings = sorted(
            meetings,
            key=lambda x: x.start_time.replace(
                tzinfo=ZoneInfo("Asia/Kolkata")) if x.start_time and x.start_time.tzinfo is None else x.start_time,
            reverse=True
        )

        local_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        result = []
        for call_record in meetings:
            seller_name = Seller.query.filter_by(phone=call_record.seller_number).first().name
            title = f"Meeting between {denormalize_phone_number(call_record.buyer_number)} and {seller_name}"
            analysis_status = 'Processing'
            direction = None
            if isinstance(call_record, Meeting):
                job_status = call_record.job.status
                if job_status in [JobStatus.INIT, JobStatus.IN_PROGRESS]:
                    analysis_status = 'Processing'
                elif job_status == JobStatus.COMPLETED:
                    analysis_status = 'Completed'
                else:
                    analysis_status = 'Not Recorded'
            elif isinstance(call_record, MobileAppCall):
                analysis_status = call_record.status
            call_record_start_time = call_record.start_time
            if call_record_start_time and call_record_start_time.tzinfo is None:
                call_record_start_time = call_record_start_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            call_record_end_time = call_record.end_time
            if call_record_end_time and call_record_end_time.tzinfo is None:
                call_record_end_time = call_record_end_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            duration = human_readable_duration(call_record_end_time, call_record_start_time)
            if isinstance(call_record, Meeting):
                title = call_record.title
                direction = call_record.direction
            elif isinstance(call_record, MobileAppCall):
                if call_record.status == 'Missed':
                    title = f'Missed Call from {denormalize_phone_number(call_record.buyer_number)}'
                    analysis_status = call_record.status
                    direction = CallDirection.INCOMING.value
                elif call_record.status == 'Not Answered':
                    title = f'{denormalize_phone_number(call_record.buyer_number)} did not answer'
                    analysis_status = call_record.status
                    direction = CallDirection.OUTGOING.value
                elif call_record.status == 'Processing':
                    start_time_local = call_record.start_time
                    if start_time_local.tzinfo is None:
                        start_time_local = start_time_local.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                    if local_now - start_time_local > timedelta(seconds=30):
                        analysis_status = 'Not Recorded'
            else:
                continue
            result.append({
                "id": str(call_record.id),
                "title": title,
                "source": call_record.source.value if isinstance(call_record, Meeting) else MeetingSource.PHONE.value,
                "deal_id": str(call_record.deal_id) if isinstance(call_record, Meeting) else None,
                "participants": call_record.participants if isinstance(call_record, Meeting) else None,
                "start_time": call_record.start_time.isoformat() if call_record.start_time else None,
                "end_time": call_record.end_time.isoformat() if call_record.end_time else None,
                "buyer_number": denormalize_phone_number(call_record.buyer_number),
                "seller_number": denormalize_phone_number(call_record.seller_number),
                "analysis_status": analysis_status,
                "duration": duration,
                "call_notes": call_record.call_notes if isinstance(call_record, Meeting) else None,
                "user_name": call_record.deal.user.name if isinstance(call_record, Meeting) else None,
                "user_email": call_record.deal.user.email if isinstance(call_record, Meeting) else None,
                "direction": direction
            })

        return jsonify(result), 200

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

        logging.info(f"Fetching call_data for meeting_id {meeting_id} for user {user_id}")

        # Join through deal to verify the meeting belongs to this user's deals
        meeting = (
            Meeting.query
            .join(Meeting.deal)
            .filter(Meeting.id == meeting_id, Deal.user_id == user_id)
            .first()
        )

        if not meeting:
            return jsonify({"error": "Meeting not found or unauthorized"}), 404

        analysis_status = meeting.job.status.value
        duration = human_readable_duration(meeting.end_time, meeting.start_time)
        result = {
            "id": str(meeting.id),
            "source": meeting.source.value,
            "title": meeting.title,
            "participants": meeting.participants,
            "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
            "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
            "status": meeting.status.value,
            "summary": meeting.summary,
            "buyer_number": denormalize_phone_number(meeting.buyer_number),
            "call_notes": meeting.call_notes,
            "deal_id": meeting.deal_id,
            "analysis_status": analysis_status,
            "duration": duration,
            "user_name": meeting.deal.user.name,
            "user_email": meeting.deal.user.email
        }

        return jsonify(result), 200

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

        # Join through deal to verify the meeting belongs to this user's deals
        meeting = (
            Meeting.query
            .join(Meeting.deal)
            .filter(Meeting.id == meeting_id, Deal.user_id == user_id)
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

        # Join through deal to verify the meeting belongs to this user's deals
        meeting = (
            Meeting.query
            .join(Meeting.deal)
            .filter(Meeting.id == meeting_id, Deal.user_id == user_id)
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
