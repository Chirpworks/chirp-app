import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from enum import Enum

import requests
from flask import Blueprint, request, jsonify
from sqlalchemy import and_

from app import Job, db, User, Meeting
from app.constants import AWSConstants, CallDirection, MeetingSource
from app.models.deal import Deal
from app.models.exotel_calls import ExotelCall
from app.models.job import JobStatus
from app.models.meeting import ProcessingStatus
from app.models.mobile_app_calls import MobileAppCall
from app.service.aws.ecs_client import ECSClient
from app.utils.call_recording_utils import upload_file_to_s3, download_exotel_file_from_url, get_audio_duration_seconds, \
    normalize_phone_number

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

        job = Job.query.get(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Update job with the recording URL
        job.recording_s3_url = recording_s3_url
        db.session.commit()

        # Initialize ECS task for speaker diarization
        ecs_client = ECSClient()
        task_response = ecs_client.run_speaker_diarization_task(job_id=job_id)

        return jsonify({
            "message": "Recording received and ECS speaker diarization task started",
            "job_id": job.id,
            "recording_s3_url": job.recording_s3_url,
            "ecs_task_response": task_response
        }), 200
    except Exception as e:
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

        call_from = normalize_phone_number(call_from)
        call_start_time = datetime.fromisoformat(call_start_time)

        # create meeting record
        # get user
        user = User.query.filter_by(phone=call_from).first()
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
        logging.info(f"call end_time set for this exotel call: {call_end_time}")

        # No matching AppCall — just store this Exotel call temporarily
        exotel_call = ExotelCall(
            call_from=call_from,
            start_time=call_start_time,
            end_time=call_end_time,
            duration=call_duration,
            call_recording_url=call_recording_url
        )
        db.session.add(exotel_call)
        db.session.commit()

        logging.info("Searching for matching mobile app call")
        # 2. Search for a matching Exotel call
        matching_app_call = (
            MobileAppCall.query
            .filter(and_(
                MobileAppCall.seller_number == call_from,
                MobileAppCall.start_time <= call_start_time,
                MobileAppCall.end_time >= call_end_time
            ))
            .order_by(MobileAppCall.start_time.asc())
            .first()
        )

        if matching_app_call:
            logging.info(f"matching app call found with id: {matching_app_call.id}")
            try:
                logging.info("Saving audio file to S3 after matching app call log has been found")
                s3_key = f"recordings/exotel/{call_from}/{matching_app_call.id or exotel_call.id}.mp3"
                bucket_name = AWSConstants.AUDIO_FILES_S3_BUCKET
                s3_url = upload_file_to_s3(temp_file_path, bucket_name, s3_key)
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            except Exception as e:
                if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                logging.info(f"Failed to upload Exotel recording: {str(e)}")
                return jsonify({"error": f"Failed to upload Exotel recording: {str(e)}"}), 500

            logging.info("Checking if deal already exists")
            deal = (
                Deal.query
                .filter_by(buyer_number=matching_app_call.buyer_number, seller_number=call_from)
                .first()
            )
            if not deal:
                logging.info("Deal doesn't already exist. Creating new deal entry")
                deal = Deal(
                    name=f"Deal between {matching_app_call.buyer_number} and {call_from}",
                    buyer_number=matching_app_call.buyer_number,
                    seller_number=call_from,
                    user_id=user.id,
                )
                db.session.add(deal)
                db.session.flush()

            logging.info("Creating new meeting and job entry for reconciled call.")
            # Create a Meeting and Job for this reconciled call
            meeting = Meeting(
                id=matching_app_call.id,
                mobile_app_call_id=matching_app_call.mobile_app_call_id,
                buyer_number=matching_app_call.buyer_number,
                seller_number=call_from,
                title=f"Meeting between {matching_app_call.buyer_number} and {call_from}",
                start_time=matching_app_call.start_time,
                scheduled_at=matching_app_call.start_time,
                status=ProcessingStatus.PROCESSING,
                deal_id=deal.id,
                source=MeetingSource.PHONE,
                participants=[call_from, matching_app_call.buyer_number],
                end_time=matching_app_call.end_time,
            )
            db.session.add(meeting)
            db.session.flush()

            job = Job(
                meeting_id=meeting.id,
                status=JobStatus.INIT,
                s3_audio_url=s3_url
            )
            db.session.add(job)
            db.session.flush()

            # Delete reconciled records
            db.session.delete(exotel_call)
            db.session.delete(matching_app_call)
            db.session.commit()

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
        logging.error({"error": f"Failed to process Exotel recording: {str(e)}"})
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

            user = User.query.filter_by(phone=seller_number).first()

            if not user:
                logging.info(f"No user with phone number {seller_number} found")
                return jsonify({"message": f"No user with phone number {seller_number} found"}), 404

            call_type = CallDirection[call_type_str.upper()]  # e.g., 'incoming' → CallDirection.INCOMING
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)
            # adding this time to enlarge the window for exotel call reconciliation
            end_time = end_time + timedelta(seconds=3)

            logging.info("Creating app call record")
            # 1. Create the mobile app call record
            mobile_call = MobileAppCall(
                mobile_app_call_id=call_id,
                buyer_number=buyer_number,
                seller_number=seller_number,
                call_type=call_type,
                start_time=start_time,
                end_time=end_time,
                duration=duration
            )
            db.session.add(mobile_call)
            db.session.commit()

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
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                except Exception as e:
                    if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                    logging.info(f"Failed to upload Exotel recording: {str(e)}")
                    return jsonify({"error": f"Failed to upload Exotel recording: {str(e)}"}), 500

                logging.info("Checking if deal already exists")
                deal = (
                    Deal.query
                    .filter_by(buyer_number=buyer_number, seller_number=seller_number)
                    .first()
                )
                if not deal:
                    logging.info("Deal doesn't already exist. Creating new deal entry")
                    deal = Deal(
                        name=f"Deal between {buyer_number} and {seller_number}",
                        buyer_number=buyer_number,
                        seller_number=seller_number,
                        user_id=user.id
                    )
                    db.session.add(deal)
                    db.session.flush()

                logging.info("Creating new meeting and job entry for reconciled call.")
                # Create a Meeting and Job for this reconciled call
                meeting = Meeting(
                    id=mobile_call.id,
                    mobile_app_call_id=call_id,
                    buyer_number=buyer_number,
                    seller_number=seller_number,
                    title=f"Meeting between {buyer_number} and {seller_number}",
                    start_time=start_time,
                    scheduled_at=start_time,
                    status=ProcessingStatus.INITIALIZED,
                    deal_id=deal.id,
                    source=MeetingSource.PHONE,
                    participants=[seller_number, buyer_number],
                    end_time=end_time,
                )
                db.session.add(meeting)
                db.session.flush()

                job = Job(
                    meeting_id=meeting.id,
                    status=JobStatus.INIT,
                    s3_audio_url=s3_url
                )
                db.session.add(job)

                # Delete reconciled records
                db.session.delete(matching_exotel_call)
                db.session.delete(mobile_call)
                db.session.commit()

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
                response = requests.post(
                    runpod_diarization_url, headers=headers, data=json.dumps(payload)
                )
                if response.status_code == 200:
                    result = response.json()
                    logging.info(f"Successfully started diarization: {str(result)}")
                else:
                    logging.error(f"Error in starting diarization: {response.status_code}, {response.text}")

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
        logging.error({"error": f"Failed to process app call records: {str(e)}"})
        db.session.rollback()  # Rollback in case of any error
        return jsonify({"error": f"Failed to process app call record: {str(e)}"}), 500
