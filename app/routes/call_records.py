import json
import traceback
from zoneinfo import ZoneInfo

import logging
import os
import uuid
from datetime import datetime, timedelta

import requests
from flask import Blueprint, request, jsonify
from sqlalchemy import and_

from app import db
from app.services import JobService, SellerService
from app.constants import AWSConstants, MeetingSource
from app.models.exotel_calls import ExotelCall

from app.external.aws.ecs_client import ECSClient
from app.utils.call_recording_utils import upload_file_to_s3, download_exotel_file_from_url, get_audio_duration_seconds, \
    normalize_phone_number, calculate_call_status, denormalize_phone_number, find_or_create_buyer
from app.services import BuyerService, SellerService, CallService, MeetingService, JobService

logging = logging.getLogger(__name__)

call_record_bp = Blueprint("call_records", __name__)


@call_record_bp.route('/post_recording', methods=['POST'])
def post_recording():
    """
    Post method for recording app to send recording details.
    This method initializes an ECS task to start transcription for the recording
    """
    try:
        data = request.get_json()
        job_id = data.get("job_id")
        recording_s3_url = data.get("recording_s3_url")

        if not job_id or not recording_s3_url:
            return jsonify({"error": "Missing required fields"}), 400

        job = JobService.get_by_id(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Update job with the recording URL
        job.s3_audio_url = recording_s3_url
        db.session.commit()

        # Initialize ECS task for speaker diarization
        ecs_client = ECSClient()
        task_response = ecs_client.run_speaker_diarization_task(job_id=job_id)

        return jsonify({
            "message": "Recording received and ECS speaker diarization task started",
            "job_id": str(job.id),
            "s3_audio_url": job.s3_audio_url,
            "ecs_task_response": task_response
        }), 200
    except Exception as e:
        logging.error(f"Failed to process recording: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return {"error": f"failed to create account. Error - {e}"}


@call_record_bp.route("/post_exotel_recording", methods=["GET"])
def post_exotel_recording():
    """
    Post method for exotel webhook to send recording details.
    This method initializes an ECS task to start transcription for the recording.
    Creates a meeting record, and a corresponding job record for tracking.
    """
    try:
        logging.info("Processing request for exotel call recording")
        call_id = request.args.get("CallSid")
        call_from = request.args.get("CallFrom")
        call_to = request.args.get("CallTo")
        call_status = request.args.get("CallStatus")
        call_direction = request.args.get("Direction")
        call_created_time = request.args.get("Created")
        call_duration = request.args.get("DialCallDuration")
        call_start_time = request.args.get("StartTime")
        call_end_time = request.args.get("EndTime")
        call_recording_url = request.args.get("RecordingUrl")

        exotel_call_recording_details = {
            "call_id": call_id,
            "call_from": call_from,
            "call_to": call_to,
            "call_status": call_status,
            "call_direction": call_direction,
            "call_created_time": call_created_time,
            "call_duration": call_duration,
            "call_start_time": call_start_time,
            "call_end_time": call_end_time,
            "call_recording_url": call_recording_url
        }

        logging.info(f"Received request to process exotel recording with details: {exotel_call_recording_details}")

        # Validate required parameters
        if not all([call_from, call_start_time, call_duration, call_recording_url]):
            return jsonify({"error": "Missing required parameters"}), 400

        # Type assertions after validation
        assert call_from is not None
        assert call_start_time is not None
        assert call_duration is not None
        assert call_recording_url is not None

        call_from = normalize_phone_number(call_from)
        call_start_time = datetime.strptime(call_start_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=ZoneInfo("Asia/Kolkata"))

        # create meeting record
        # get user using SellerService
        user = SellerService.get_by_phone(call_from)
        if not user:
            logging.error({"error": f"No user found with phone number: {call_from}"})
            return jsonify({"error": f"No user found with phone number: {call_from}"}), 404

        logging.info("Downloading exotel audio file")
        temp_file_path = download_exotel_file_from_url(call_recording_url)

        duration_seconds = get_audio_duration_seconds(temp_file_path)

        if duration_seconds < 5:
            logging.error({"error": f"Call duration too low to process: {duration_seconds} seconds"})
            return jsonify({"error": f"Failed to process Exotel recording"}), 500

        logging.info(f"duration of recorded audio file is {duration_seconds}")
        call_end_time = call_start_time + timedelta(seconds=duration_seconds)

        logging.info(f"Creating Exotel call record for user {user.email}")
        # No matching AppCall — just store this Exotel call temporarily using CallService
        exotel_call = CallService.create_exotel_call(
            call_from=call_from,
            start_time=call_start_time,
            end_time=call_end_time,
            duration=int(call_duration) if call_duration else 0,
            call_recording_url=call_recording_url
        )

        logging.info("Searching for matching mobile app call")
        # Search for a matching mobile app call using CallService
        matching_app_call = CallService.find_matching_mobile_app_call(
            seller_number=call_from,
            start_time=call_start_time,
            end_time=call_end_time
        )

        if matching_app_call:
            logging.info(f"matching app call found with id: {matching_app_call.id}")
            try:
                logging.info("Saving audio file to S3 after matching app call log has been found")
                s3_key = f"recordings/exotel/{call_from}/{matching_app_call.id or exotel_call.id}.mp3"
                bucket_name = AWSConstants.AUDIO_FILES_S3_BUCKET
                s3_url = upload_file_to_s3(temp_file_path, bucket_name, s3_key)
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            except Exception as e:
                if 'temp_file_path' in locals() and temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                logging.error(f"Failed to upload Exotel recording: {str(e)}")
                logging.error(f"Traceback: {traceback.format_exc()}")
                return jsonify({"error": f"Failed to upload Exotel recording: {str(e)}"}), 500

            logging.info(f"Creating new meeting and job entry for reconciled call for user {user.email}")
            
            # Find or create buyer using BuyerService
            buyer = BuyerService.find_or_create_buyer(matching_app_call.buyer_number, user.agency_id)
            
            # Create Meeting using MeetingService
            meeting = MeetingService.create_meeting(
                buyer_id=buyer.id,
                seller_id=user.id,
                title=f"Meeting between {denormalize_phone_number(matching_app_call.buyer_number)} and {user.name}",
                start_time=matching_app_call.start_time,
                end_time=matching_app_call.end_time,
                source=MeetingSource.PHONE,
                direction=matching_app_call.call_type,
                mobile_app_call_id=matching_app_call.mobile_app_call_id,
                participants=[call_from, matching_app_call.buyer_number],
                scheduled_at=matching_app_call.start_time,

            )
            
            # Create Job using JobService
            job = JobService.create_job(
                meeting_id=meeting.id,
                s3_audio_url=s3_url,
                start_time=call_start_time
            )

            # Delete reconciled records using CallService
            CallService.delete_exotel_call(exotel_call)
            CallService.delete_mobile_app_call(matching_app_call)

            logging.info("Initializing task for diarization.")
            # Initialize ECS task for speaker diarization
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer rpa_2BLBUZNNJ8ME90LK3OA517U24ZTT4EP4WQ9LPYLR13nqf3"
            }
            payload = {
                "input": {
                    "job_id": str(job.id),
                }
            }
            runpod_diarization_url = os.getenv("RUNPOD_DIARIZATION_URL")
            if not runpod_diarization_url:
                logging.error("RUNPOD_DIARIZATION_URL environment variable not set")
                return jsonify({"error": "Diarization service not configured"}), 500
            
            response = requests.post(
                runpod_diarization_url, headers=headers, data=json.dumps(payload)
            )
            if response.status_code == 200:
                result = response.json()
                logging.info(f"Successfully started diarization: {str(result)}")
            else:
                logging.error(f"Error in starting diarization: {response.status_code}, {response.text}")
        else:
            logging.info(f"No matching app call found. Saving in Exotel call temp table with id {exotel_call.id}")

        return jsonify({"message": f"Exotel call record processed successfully."}), 200

    except Exception as e:
        logging.error(f"Failed to process Exotel recording: %s", traceback.format_exc())
        db.session.rollback()  # Rollback in case of any error
        return jsonify({"error": f"Failed to process Exotel recording: {str(e)}"}), 500


@call_record_bp.route("/post_app_call_record", methods=["POST"])
def post_app_call_record():
    try:
        data = request.get_json()
        logging.info(f"Received POST request for processing app call logs with data: {data}")
        for item in data:
            seller_number = item.get("sellerNumber")
            call_id = item.get("appCallId")  # Not stored directly; kept here if needed later
            buyer_number = item.get("buyerNumber")
            call_type_str = item.get("callType")
            start_time_str = item.get("startTime")
            end_time_str = item.get("endTime")
            duration = item.get("duration")

            if not all([buyer_number, seller_number, call_type_str, start_time_str, duration]):
                logging.error("all required fields were not sent in the request parameter")
                return jsonify({"error": "Missing required fields"}), 400

            user = SellerService.get_by_phone(seller_number)

            if not user:
                logging.info(f"No user with phone number {seller_number} found")
                return jsonify({"message": f"No user with phone number {seller_number} found"}), 404

            buyer_number = normalize_phone_number(buyer_number)
            seller_number = normalize_phone_number(seller_number)

            # call_type = CallDirection[call_type_str.upper()]  # e.g., 'incoming' → CallDirection.INCOMING
            start_time_str = datetime.strptime(start_time_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
            start_time = start_time_str.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            end_time_str = datetime.strptime(end_time_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
            end_time = end_time_str.replace(tzinfo=ZoneInfo("Asia/Kolkata"))

            call_status = calculate_call_status(call_type_str, duration)

            if call_status == 'Processing' and duration != '0':
                # adding this time to enlarge the window for exotel call reconciliation
                end_time = end_time + timedelta(seconds=3)

            logging.info(f"Creating app call record for user {user.email}")
            # 1. Create the mobile app call record
            mobile_call = CallService.create_mobile_app_call(
                mobile_app_call_id=call_id,
                buyer_number=buyer_number,
                seller_number=seller_number,
                call_type=call_type_str,
                start_time=start_time,
                end_time=end_time,
                duration=int(duration) if duration else 0,
                user_id=user.id
            )

            logging.info("Searching for matching exotel call")
            # 2. Search for a matching Exotel call
            matching_exotel_call = (
                ExotelCall.query
                .filter(and_(
                    ExotelCall.call_from == seller_number,
                    ExotelCall.start_time >= start_time,
                    ExotelCall.end_time <= end_time,
                ))
                .order_by(ExotelCall.start_time.asc())
                .first()
            )

            if matching_exotel_call:
                logging.info(f"matching exotel call found with id: {matching_exotel_call.id}")
                try:
                    logging.info("Downloading exotel file and saving to S3")
                    temp_file_path = download_exotel_file_from_url(matching_exotel_call.call_recording_url)
                    s3_key = f"recordings/exotel/{seller_number}/{call_id or uuid.uuid4()}.mp3"
                    bucket_name = AWSConstants.AUDIO_FILES_S3_BUCKET
                    s3_url = upload_file_to_s3(temp_file_path, bucket_name, s3_key)
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                except Exception as e:
                    if 'temp_file_path' in locals() and temp_file_path and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                    logging.error(f"Failed to upload Exotel recording: {str(e)}")
                    logging.error(f"Traceback: {traceback.format_exc()}")
                    return jsonify({"error": f"Failed to upload Exotel recording: {str(e)}"}), 500

                logging.info("Creating new meeting and job entry for reconciled call.")
                
                # Find or create buyer
                buyer = find_or_create_buyer(buyer_number, user.agency_id)
                
                # Create Meeting using MeetingService
                meeting = MeetingService.create_meeting(
                    buyer_id=buyer.id,
                    seller_id=user.id,
                    title=f"Meeting between {denormalize_phone_number(buyer_number)} and {user.name}",
                    start_time=start_time,
                    end_time=end_time,
                    source=MeetingSource.PHONE,
                    direction=mobile_call.call_type,
                    mobile_app_call_id=call_id,
                    participants=[seller_number, buyer_number],
                    scheduled_at=start_time
                )

                # Create Job using JobService  
                job = JobService.create_job(
                    meeting_id=meeting.id,
                    s3_audio_url=s3_url
                )

                # Delete reconciled records
                db.session.delete(matching_exotel_call)
                db.session.delete(mobile_call)

                logging.info("Initializing ECS task for diarization.")
                # Initialize ECS task for speaker diarization
                # ecs_client = ECSClient()
                # task_response = ecs_client.run_speaker_diarization_task(job_id=job.id)
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer rpa_2BLBUZNNJ8ME90LK3OA517U24ZTT4EP4WQ9LPYLR13nqf3"
                }
                payload = {
                    "input": {
                        "job_id": str(job.id),
                    }
                }
                runpod_diarization_url = os.getenv("RUNPOD_DIARIZATION_URL")
                if runpod_diarization_url:
                    response = requests.post(
                        runpod_diarization_url, headers=headers, data=json.dumps(payload)
                    )
                    if response.status_code == 200:
                        result = response.json()
                        logging.info(f"Successfully started diarization: {str(result)}")
                    else:
                        logging.error(f"Error in starting diarization: {response.status_code}, {response.text}")
                else:
                    logging.error("RUNPOD_DIARIZATION_URL environment variable not set")

                logging.info(f"Intialized task for diarization for appcallID: {meeting.mobile_app_call_id}")
            else:
                logging.info(
                    f"No matching Exotel call found. Mobile call saved for future reconciliation with id: {mobile_call.id}"
                )

        logging.info("Successfully processed all app call logs")
        return jsonify(
            {"message": f"Mobile app call records processed successfully."}
        ), 200
    except Exception as e:
        logging.error("Failed to process app call records %s", traceback.format_exc())
        db.session.rollback()  # Rollback in case of any error
        return jsonify({"error": f"Failed to process app call record: {str(e)}"}), 500
