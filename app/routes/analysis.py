import logging
import traceback
import requests
from flask import Blueprint, request, jsonify

from app.services import JobService, MeetingService
from app.models.job import JobStatus

logging = logging.getLogger(__name__)

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.route("/trigger_analysis", methods=["POST"])
def trigger_analysis():
    job_id = None
    try:
        logging.info(f"Triggering analysis")
        data = request.json
        if not data:
            return jsonify({"error": "Missing request data"}), 400
        job_id = data.get("job_id")
        logging.info(f"Processing analysis for Job ID: {job_id}")

        if not job_id:
            return jsonify({"error": "Missing job_id"}), 400

        job = JobService.get_by_id(job_id)
        if not job:
            logging.error(f"Job with id {job_id} not found")
            return jsonify({"error": f"Job with id {job_id} not found"}), 404

        meeting = JobService.get_meeting_by_job_id(job_id)
        if not meeting:
            logging.error(f"Meeting for job {job_id} not found")
            return jsonify({"error": f"Meeting for job {job_id} not found"}), 404
        # Check if job is completed and transcription is available
        if job.status != JobStatus.COMPLETED:
            logging.error(f"Job with id {job_id} is not completed. Current status: {job.status}")
            return jsonify({"error": f"Job with id {job_id} is not completed. Current status: {job.status}"}), 400
            
        if not meeting.transcription:
            logging.error(f"Meeting with id {str(meeting.id)} is missing transcription data")
            return jsonify({"error": f"Meeting with id {str(meeting.id)} is missing transcription data"}), 400

        # Call Google RunCloud API for analysis
        buyer_id = str(meeting.buyer_id)
        meeting_id = str(meeting.id)
        
        # TODO: Replace with actual Google RunCloud endpoint URL
        runcloud_url = "https://call-analysis-pipeline-dev-109365356440.europe-west1.run.app"
        
        try:
            response = requests.post(runcloud_url, json={
                "buyerId": buyer_id,
                "callId": meeting_id
            })
            response.raise_for_status()
            logging.info(f"Successfully triggered analysis via RunCloud API for job_id: {job_id}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to call RunCloud API for job_id {job_id}: {e}")
            return jsonify({"error": f"Failed to trigger analysis via RunCloud API: {str(e)}"}), 500

        return jsonify({"message": f"Analysis task triggered successfully for job_id: {job_id}"}), 200
    except Exception as e:
        logging.error(f"Failed to trigger analysis for Job ID: {job_id} with error: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to trigger call analysis: {str(e)}"}), 500
