import traceback
from typing import Union

import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.services import SellerService, MeetingService, CallService, ActionService, CallPerformanceService
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

        # Parse date range parameters (supports both new start_date/end_date and legacy time_frame)
        start_date, end_date, error = parse_date_range_params(default_days_back=0)
        if error:
            return jsonify(error[0]), error[1]

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
            "overall_summary": meeting_data.overall_summary,
            "type": meeting_data.type,
            "detected_call_type": getattr(meeting_data, 'detected_call_type', None),
            "detected_products": getattr(meeting_data, 'detected_products', None),
            "job": {
                "id": str(meeting_data.job.id),
                "status": meeting_data.job.status.value if meeting_data.job.status else None,
                "start_time": meeting_data.job.start_time.isoformat() if meeting_data.job.start_time else None,
                "end_time": meeting_data.job.end_time.isoformat() if meeting_data.job.end_time else None
            } if meeting_data.job else None,
            "performance": None,
        }

        # Get performance data with analysis fields using the service
        performance_summary = CallPerformanceService.get_performance_summary(meeting_id)
        if performance_summary:
            meeting_dict["performance"] = performance_summary

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
        logging.info(f"[UPDATE_SUMMARY] Starting update for meeting_id: {meeting_id}")

        data = request.get_json()
        if not data:
            logging.error(f"[UPDATE_SUMMARY] No data provided for meeting_id: {meeting_id}")
            return jsonify({"error": "No data provided"}), 400
            
        # Log comprehensive input data for debugging
        logging.info(f"[UPDATE_SUMMARY] Raw input data for meeting {meeting_id}: {data}")
        logging.info(f"[UPDATE_SUMMARY] Input data keys: {list(data.keys())}")
        logging.info(f"[UPDATE_SUMMARY] Input data types: {[(k, type(v).__name__) for k, v in data.items()]}")

        meeting = MeetingService.get_by_id(meeting_id)
        if not meeting:
            logging.error(f"[UPDATE_SUMMARY] Meeting not found: {meeting_id}")
            return jsonify({"error": "Meeting not found"}), 404

        logging.info(f"[UPDATE_SUMMARY] Found meeting {meeting_id} - buyer_id: {meeting.buyer_id}, seller_id: {meeting.seller_id}")

        # Prepare a dictionary to hold all updates for the meeting
        update_data = {}

        # Get top-level fields: callTitle and callType
        if "call_title" in data:
            update_data["title"] = data["call_title"]
            logging.info(f"[UPDATE_SUMMARY] Will update title: '{data['call_title']}'")
        if "call_type" in data:
            update_data["type"] = data["call_type"]
            logging.info(f"[UPDATE_SUMMARY] Will update type: '{data['call_type']}'")

        # Get detected fields from AI analysis
        if "detected_call_type" in data:
            update_data["detected_call_type"] = data["detected_call_type"]
            logging.info(f"[UPDATE_SUMMARY] Will update detected_call_type: '{data['detected_call_type']}'")
        
        if "detected_products" in data:
            update_data["detected_products"] = data["detected_products"]
            logging.info(f"[UPDATE_SUMMARY] Will update detected_products: '{data['detected_products']}'")

        # Process callSummary if it exists - make a copy to avoid mutating original data
        call_summary = data.get("call_summary")
        if call_summary:
            logging.info(f"[UPDATE_SUMMARY] Processing call_summary of type: {type(call_summary).__name__}")
            if isinstance(call_summary, dict):
                # Make a copy to avoid mutating the original data
                call_summary_copy = call_summary.copy()
                logging.info(f"[UPDATE_SUMMARY] call_summary keys: {list(call_summary_copy.keys())}")
                
                # Extract specific keys for individual columns and remove them from the summary dict
                llm_fields_to_extract = [
                    "call_purpose", "key_discussion_points", "buyer_pain_points",
                    "solutions_discussed", "risks", "overall_summary"
                ]
                extracted_fields = {}
                for field in llm_fields_to_extract:
                    if field in call_summary_copy:
                        extracted_fields[field] = call_summary_copy.pop(field)
                        update_data[field] = extracted_fields[field]
                        logging.info(f"[UPDATE_SUMMARY] Extracted {field}: {len(str(extracted_fields[field]))} chars")
                
                # The remainder of the call_summary object is saved to the summary field
                update_data["summary"] = call_summary_copy
                logging.info(f"[UPDATE_SUMMARY] Remaining summary data keys: {list(call_summary_copy.keys())}")
            else:
                logging.warning(f"[UPDATE_SUMMARY] call_summary is not a dict (type: {type(call_summary).__name__}), storing as-is")
                update_data["summary"] = call_summary

        logging.info(f"[UPDATE_SUMMARY] Final update_data keys: {list(update_data.keys())}")
        logging.info(f"[UPDATE_SUMMARY] Will update {len(update_data)} meeting fields")

        # Start transaction for atomic operations
        updated_meeting = None
        created_action_ids = []
        actions_to_create = data.get("actions", [])
        
        try:
            # Update the meeting with all collected data
            if update_data:
                logging.info(f"[UPDATE_SUMMARY] Attempting to update meeting {meeting_id} with data: {update_data}")
                updated_meeting = MeetingService.update_llm_analysis(meeting_id, update_data)
                if not updated_meeting:
                    logging.error(f"[UPDATE_SUMMARY] MeetingService.update_llm_analysis returned None for meeting {meeting_id}")
                    return jsonify({"error": "Failed to update meeting"}), 500
                logging.info(f"[UPDATE_SUMMARY] Successfully updated meeting {meeting_id}")
            else:
                updated_meeting = meeting # No updates were made
                logging.info(f"[UPDATE_SUMMARY] No meeting updates needed for {meeting_id}")

            # Create actions if any were found
            if actions_to_create:
                logging.info(f"[UPDATE_SUMMARY] Processing {len(actions_to_create)} actions for meeting {meeting_id}")
                kolkata_tz = ZoneInfo("Asia/Kolkata")

                for i, action_item in enumerate(actions_to_create):
                    logging.info(f"[UPDATE_SUMMARY] Processing action {i+1}/{len(actions_to_create)}: {action_item}")
                    
                    title = action_item.get("action_name")
                    if not title:
                        logging.warning(f"[UPDATE_SUMMARY] Skipping action {i+1} due to missing 'action_name': {action_item}")
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
                            logging.info(f"[UPDATE_SUMMARY] Parsed due_date for action '{title}': {due_date}")
                        except ValueError as date_error:
                            logging.warning(f"[UPDATE_SUMMARY] Could not parse due_date '{due_date_str}' for action '{title}': {date_error}")

                    try:
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
                        logging.info(f"[UPDATE_SUMMARY] Created action {i+1} with ID: {new_action.id}")
                    except Exception as action_error:
                        logging.error(f"[UPDATE_SUMMARY] Failed to create action {i+1} '{title}': {action_error}")
                        # Continue processing other actions rather than failing completely
                        continue
            else:
                logging.info(f"[UPDATE_SUMMARY] No actions to create for meeting {meeting_id}")

        except Exception as update_error:
            logging.error(f"[UPDATE_SUMMARY] Transaction failed for meeting {meeting_id}: {update_error}")
            logging.error(f"[UPDATE_SUMMARY] Transaction error traceback: {traceback.format_exc()}")
            # If we had a partial success (meeting updated but actions failed), 
            # this could lead to inconsistent state. The BaseService handles rollback.
            raise

        response = {
            "id": str(updated_meeting.id),
            "message": "Meeting analysis data updated successfully",
            "updated_fields": list(update_data.keys()),
            "actions_created": len(created_action_ids),
            "created_action_ids": created_action_ids
        }

        logging.info(f"[UPDATE_SUMMARY] Successfully completed update for meeting {meeting_id}")
        logging.info(f"[UPDATE_SUMMARY] Response: {response}")

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"[UPDATE_SUMMARY] Fatal error for meeting_id {meeting_id}: {e}")
        logging.error(f"[UPDATE_SUMMARY] Full traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to update meeting analysis: {str(e)}"}), 500
