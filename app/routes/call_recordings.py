from typing import List, Union

from flask import Blueprint, request, jsonify

from app import Job, db
from app.service.aws.ecs_client import ECSClient

recording_bp = Blueprint("call_recordings", __name__)


@recording_bp.route('/post_recording', methods=['POST'])
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
