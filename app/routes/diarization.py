import logging
import os
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify

from app import Job, db, User, Meeting
from app.constants import AWSConstants
from app.models.job import JobStatus
from app.service.aws.ecs_client import ECSClient
from app.utils.call_recording_utils import download_file_from_url, upload_file_to_s3, download_exotel_file_from_url

logging = logging.getLogger(__name__)

recording_bp = Blueprint("call_recordings", __name__)


@recording_bp.route('/diarization', methods=['POST'])
def retry_diarization():
    """
    Post method for recording app to send recording details.
    This method initializes an ECS task to start transcription for the recording
    """
    try:
        data = request.get_json()
        job_id = data.get("job_id")

        if not job_id:
            return jsonify({"error": "Missing required fields"}), 400

        job = Job.query.get(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Initialize ECS task for speaker diarization
        ecs_client = ECSClient()
        task_response = ecs_client.run_speaker_diarization_task(job_id=job_id)

        return jsonify({
            "message": "Recording received and ECS speaker diarization task started",
            "job_id": job.id,
            "ecs_task_response": task_response
        }), 200
    except Exception as e:
        return {"error": f"failed to create account. Error - {e}"}
