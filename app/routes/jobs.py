import logging
import traceback
from flask import Blueprint, jsonify, request

from app.services import JobService
from app.models.job import JobStatus

logging = logging.getLogger(__name__)

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.route("/update_status", methods=["POST"])
def update_job_status():
    """
    Update job status via API endpoint.
    This endpoint is used by external services (like diarization scripts) to update job status.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing request data"}), 400
            
        job_id = data.get("job_id")
        status = data.get("status")
        
        if not job_id:
            return jsonify({"error": "Missing job_id"}), 400
            
        if not status:
            return jsonify({"error": "Missing status"}), 400
            
        # Validate status is a valid JobStatus enum value
        try:
            job_status = JobStatus(status)
        except ValueError:
            valid_statuses = [s.value for s in JobStatus]
            return jsonify({
                "error": f"Invalid status: {status}. Valid statuses are: {valid_statuses}"
            }), 400
        
        # Update job status using JobService
        job = JobService.update_status(job_id, job_status)
        
        if not job:
            return jsonify({"error": f"Job with id {job_id} not found"}), 404
            
        return jsonify({
            "message": f"Job {job_id} status updated to {status}",
            "job_id": str(job.id),
            "status": job.status.value,
            "start_time": job.start_time.isoformat() if job.start_time else None,
            "end_time": job.end_time.isoformat() if job.end_time else None
        }), 200
        
    except Exception as e:
        logging.error(f"Failed to update job status: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to update job status: {str(e)}"}), 500


@jobs_bp.route("/<job_id>/status", methods=["GET"])
def get_job_status(job_id):
    """
    Get current job status.
    """
    try:
        job = JobService.get_by_id(job_id)
        
        if not job:
            return jsonify({"error": f"Job with id {job_id} not found"}), 404
            
        return jsonify({
            "job_id": str(job.id),
            "status": job.status.value,
            "start_time": job.start_time.isoformat() if job.start_time else None,
            "end_time": job.end_time.isoformat() if job.end_time else None,
            "s3_audio_url": job.s3_audio_url
        }), 200
        
    except Exception as e:
        logging.error(f"Failed to get job status: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to get job status: {str(e)}"}), 500


@jobs_bp.route("/<job_id>/audio_url", methods=["GET"])
def get_job_audio_url(job_id):
    """
    Get S3 audio URL for a job.
    """
    try:
        job = JobService.get_by_id(job_id)
        
        if not job:
            return jsonify({"error": f"Job with id {job_id} not found"}), 404
            
        if not job.s3_audio_url:
            return jsonify({"error": "No audio URL found for this job"}), 404
        
        return jsonify({
            "job_id": str(job.id),
            "s3_audio_url": job.s3_audio_url
        }), 200
        
    except Exception as e:
        logging.error(f"Failed to get audio URL for job {job_id}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to get audio URL: {str(e)}"}), 500


@jobs_bp.route("/<job_id>/meeting/transcription", methods=["PUT"])
def update_meeting_transcription(job_id):
    """
    Update meeting transcription for a job.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing request data"}), 400
            
        transcription = data.get("transcription")
        if transcription is None:
            return jsonify({"error": "Missing transcription data"}), 400
        
        job = JobService.get_by_id(job_id)
        if not job:
            return jsonify({"error": f"Job with id {job_id} not found"}), 404
        
        if not job.meeting_id:
            return jsonify({"error": "No meeting associated with this job"}), 404
        
        # Import here to avoid circular imports
        from app.services.meeting_service import MeetingService
        
        meeting = MeetingService.get_by_id(job.meeting_id)
        if not meeting:
            return jsonify({"error": f"Meeting with id {job.meeting_id} not found"}), 404
        
        # Update meeting transcription
        updated_meeting = MeetingService.update_transcription(meeting.id, transcription)
        
        return jsonify({
            "message": f"Meeting transcription updated for job {job_id}",
            "job_id": str(job.id),
            "meeting_id": str(meeting.id),
            "transcription_updated": True
        }), 200
        
    except Exception as e:
        logging.error(f"Failed to update meeting transcription for job {job_id}: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to update meeting transcription: {str(e)}"}), 500
