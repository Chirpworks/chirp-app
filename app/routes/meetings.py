import traceback
from typing import Union

import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.services import SellerService, MeetingService, CallService, ActionService
from app.models.seller import SellerRole
from app.external.google_calendar.google_calendar_user import GoogleCalendarUserService
from app.utils.time_utils import get_date_range_from_timeframe, validate_time_frame, parse_date_range_params
from datetime import datetime
from zoneinfo import ZoneInfo

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

        # Parse date range parameters with backward compatibility
        start_date, end_date, error = parse_date_range_params(default_days_back=0)
        if error:
            return jsonify({"error": error[0]}), error[1]

        team_member_ids = request.args.getlist("team_member_ids")
        if team_member_ids:
            user = SellerService.get_by_id(user_id)
            if not user:
                logging.error("User not found; unauthorized")
                return jsonify({"error": "User not found or unauthorized"}), 404
            if user.role != SellerRole.MANAGER:
                logging.info(f"Unauthorized User. 'team_member_ids' query parameter is only applicable for a manager.")
                return jsonify(
                    {"error": "Unauthorized User: 'team_member_ids' query parameter is only applicable for a manager"}
                )

            # Validate team member IDs
            for member_id in team_member_ids:
                member = SellerService.get_by_id(member_id)
                if not member:
                    logging.error(f"Seller with id {member_id} not found; unauthorized")
                    return jsonify({"error": "Seller not found or unauthorized"}), 404
            logging.info(f"Fetching call history for users {team_member_ids}")
        
        # Use MeetingService to get call history with time filtering
        call_history = MeetingService.get_call_history(user_id, team_member_ids, start_date, end_date)
        
        return jsonify(call_history), 200

    except Exception as e:
        logging.error("Failed to fetch call history: %s", traceback.format_exc())
        return jsonify({"error": f"Failed to fetch call history: {str(e)}"}), 500


@meetings_bp.route("/call_data/<uuid:meeting_id>", methods=["GET"])
@jwt_required()
def get_meeting_by_id(meeting_id):
    try:
        user_id = get_jwt_identity()

        logging.info(f"Fetching call_data for meeting_id {meeting_id} for user {user_id}")

        # Use MeetingService to get meeting with job details
        meeting_data = MeetingService.get_meeting_with_job(meeting_id)
        if not meeting_data:
            return jsonify({"error": "Meeting not found"}), 404
            
        # Verify user has access to this meeting
        # Managers can access any meeting, others can only access their own meetings
        user = SellerService.get_by_id(user_id)
        if user and user.role == SellerRole.MANAGER:
            logging.info(f"Manager {user_id} accessing meeting {meeting_id}")
        elif str(meeting_data.seller_id) != user_id:
            return jsonify({"error": "Meeting not found or unauthorized"}), 404

        # Convert Meeting model to dictionary for JSON serialization
        meeting_dict = {
            "id": str(meeting_data.id),
            "mobile_app_call_id": meeting_data.mobile_app_call_id,
            "buyer_id": str(meeting_data.buyer_id),
            "seller_id": str(meeting_data.seller_id),
            "source": meeting_data.source.value if meeting_data.source else None,
            "start_time": meeting_data.start_time.isoformat() if meeting_data.start_time else None,
            "end_time": meeting_data.end_time.isoformat() if meeting_data.end_time else None,
            "transcription": meeting_data.transcription,
            "direction": meeting_data.direction,
            "title": meeting_data.title,
            "call_purpose": meeting_data.call_purpose,
            "key_discussion_points": meeting_data.key_discussion_points,
            "buyer_pain_points": meeting_data.buyer_pain_points,
            "solutions_discussed": meeting_data.solutions_discussed,
            "risks": meeting_data.risks,
            "summary": meeting_data.summary,
            "type": meeting_data.type,
            "job": {
                "id": str(meeting_data.job.id),
                "status": meeting_data.job.status.value if meeting_data.job.status else None,
                "start_time": meeting_data.job.start_time.isoformat() if meeting_data.job.start_time else None,
                "end_time": meeting_data.job.end_time.isoformat() if meeting_data.job.end_time else None
            } if meeting_data.job else None,
        }

        # Add call performance data if it exists
        if meeting_data.call_performance:
            performance = meeting_data.call_performance
            performance_dict = {
                "overall_score": performance.overall_score,
                "analyzed_at": performance.analyzed_at.isoformat() if performance.analyzed_at else None,
                "metrics": {}
            }
            
            # Add individual metrics
            for metric in performance.get_metric_names():
                metric_data = getattr(performance, metric)
                if metric_data:
                    performance_dict['metrics'][metric] = metric_data
            
            meeting_dict["call_performance"] = performance_dict
        else:
            meeting_dict["call_performance"] = None

        return jsonify(meeting_dict), 200

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


@meetings_bp.route("/last_synced_call_timestamp", methods=["GET"])
def get_last_synced_call_timestamp():
    try:
        seller_number = request.args.get("sellerNumber")
        if not seller_number:
            return jsonify({"error": "Missing sellerNumber parameter"}), 400
            
        logging.info(f"getting last synced call timestamp for phone: {seller_number}")

        user = SellerService.get_by_phone(seller_number)
        if not user:
            logging.info(f"user not found for phone {seller_number}")
            return jsonify({"message": f"No user with phone number {seller_number} found"}), 404

        last_app_call = CallService.get_last_mobile_app_call_by_seller(seller_number)

        last_meeting = MeetingService.get_last_meeting_by_seller(user.id)

        if last_app_call and not last_meeting:
            # Convert to Asia/Kolkata timezone if not already
            app_call_time = last_app_call.start_time
            if app_call_time.tzinfo is None:
                app_call_time = app_call_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            else:
                app_call_time = app_call_time.astimezone(ZoneInfo("Asia/Kolkata"))
            
            logging.info(f"last synced call timestamp returned: {app_call_time}")
            return jsonify(
                {"source": "mobile_app_call", "last_synced_call_timestamp": app_call_time.isoformat()}
            ), 200
        elif last_meeting and not last_app_call:
            # Convert to Asia/Kolkata timezone if not already
            meeting_time = last_meeting.start_time
            if meeting_time.tzinfo is None:
                meeting_time = meeting_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            else:
                meeting_time = meeting_time.astimezone(ZoneInfo("Asia/Kolkata"))
            
            logging.info(f"last synced call timestamp returned: {meeting_time}")
            return jsonify({"source": "meeting", "last_synced_call_timestamp": meeting_time.isoformat()}), 200
        elif last_app_call and last_meeting:
            if last_app_call.start_time > last_meeting.start_time:
                # Convert to Asia/Kolkata timezone if not already
                app_call_time = last_app_call.start_time
                if app_call_time.tzinfo is None:
                    app_call_time = app_call_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                else:
                    app_call_time = app_call_time.astimezone(ZoneInfo("Asia/Kolkata"))
                
                logging.info(f"last synced call timestamp returned: {app_call_time}")
                return jsonify(
                    {"source": "mobile_app_call", "last_synced_call_timestamp": app_call_time.isoformat()}
                ), 200
            else:
                # Convert to Asia/Kolkata timezone if not already
                meeting_time = last_meeting.start_time
                if meeting_time.tzinfo is None:
                    meeting_time = meeting_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                else:
                    meeting_time = meeting_time.astimezone(ZoneInfo("Asia/Kolkata"))
                
                logging.info(f"last synced call timestamp returned: {meeting_time}")
                return jsonify({"source": "meeting", "last_synced_call_timestamp": meeting_time.isoformat()}), 200
        else:
            logging.info("No synced calls found")
            return jsonify({"message": "No synced calls found", "last_synced_call_timestamp": None}), 200

    except Exception as e:
        logging.error(f"Failed to fetch last synced call timestamp: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch last synced call timestamp: {str(e)}"}), 500


@meetings_bp.route("/call_data/summary/<uuid:meeting_id>", methods=["PUT"])
def update_meeting_summary(meeting_id):
    """
    Update call summary, title, type, and other analysis fields for a specific meeting,
    and create associated actions.
    """
    try:
        logging.info(f"Updating call analysis data for meeting_id {meeting_id}")

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        logging.info(f"Received update summary data from Pipeline: {data}")

        meeting = MeetingService.get_by_id(meeting_id)
        if not meeting:
            return jsonify({"error": "Meeting not found"}), 404

        # Prepare a dictionary to hold all updates for the meeting
        update_data = {}

        # Get top-level fields: callTitle and callType
        if "call_title" in data:
            update_data["title"] = data["call_title"]
        if "call_type" in data:
            update_data["type"] = data["call_type"]

        # Process callSummary if it exists
        call_summary = data.get("call_summary")
        actions_to_create = []

        if isinstance(call_summary, dict):
            # Extract specific keys for individual columns and remove them from the summary dict
            llm_fields_to_extract = [
                "call_purpose", "key_discussion_points", "buyer_pain_points",
                "solutions_discussed", "risks"
            ]
            for field in llm_fields_to_extract:
                if field in call_summary:
                    update_data[field] = call_summary.pop(field)
            
            # The remainder of the call_summary object is saved to the summary field
            update_data["summary"] = call_summary

        # Update the meeting with all collected data
        if update_data:
            updated_meeting = MeetingService.update_llm_analysis(meeting_id, update_data)
            if not updated_meeting:
                return jsonify({"error": "Failed to update meeting"}), 500
        else:
            updated_meeting = meeting # No updates were made

        # Create actions if any were found
        actions_to_create = data.get("actions")
        created_action_ids = []
        if actions_to_create:
            logging.info(f"Found {len(actions_to_create)} actions to create for meeting {meeting_id}")
            kolkata_tz = ZoneInfo("Asia/Kolkata")

            for action_item in actions_to_create:
                title = action_item.get("action_name")
                if not title:
                    logging.warning(f"Skipping action item due to missing 'action_name': {action_item}")
                    continue

                due_date_str = action_item.get("due_date")
                due_date = None
                if due_date_str:
                    try:
                        parsed_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                        if parsed_date.tzinfo is None:
                            due_date = parsed_date.replace(tzinfo=ZoneInfo("UTC")).astimezone(kolkata_tz)
                        else:
                            due_date = parsed_date.astimezone(kolkata_tz)
                    except ValueError:
                        logging.warning(f"Could not parse due_date '{due_date_str}'. Skipping due date for action '{title}'.")

                new_action = ActionService.create_action(
                    title=title,
                    meeting_id=str(meeting_id),
                    buyer_id=str(meeting.buyer_id),
                    seller_id=str(meeting.seller_id),
                    due_date=due_date,
                    description={"text": action_item.get("description")},
                    reasoning=action_item.get("reasoning"),
                    signals=action_item.get("signals")
                )
                created_action_ids.append(str(new_action.id))

        response = {
            "id": str(updated_meeting.id),
            "message": "Meeting analysis data updated successfully",
            "updated_fields": list(update_data.keys()),
            "actions_created": len(created_action_ids),
            "created_action_ids": created_action_ids
        }

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Failed to update meeting analysis for meeting_id {meeting_id}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to update meeting analysis: {str(e)}"}), 500
