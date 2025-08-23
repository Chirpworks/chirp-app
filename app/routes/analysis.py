import logging
import traceback
import requests
import os
import threading
from flask import Blueprint, request, jsonify

from app.services import JobService, MeetingService
from app.models.job import JobStatus

logging = logging.getLogger(__name__)

analysis_bp = Blueprint("analysis", __name__)


def _trigger_analysis_async(runcloud_url, payload, job_id, agency_id):
    """
    Helper function to trigger analysis in a separate thread.
    This runs independently of the main request.
    """
    try:
        logging.info(f"Starting async analysis trigger for job_id: {job_id}")
        response = requests.post(
            runcloud_url,
            json=payload,
            timeout=30,
            verify=True
        )
        response.raise_for_status()
        logging.info(f"Async analysis completed successfully for job_id: {job_id}")
    except Exception as e:
        logging.error(f"Async analysis failed for job_id {job_id}: {e}")
        # Don't raise the exception since this is running in a separate thread


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
        # Check if job has transcription available (allow IN_PROGRESS status after transcription)
        if job.status not in [JobStatus.COMPLETED, JobStatus.IN_PROGRESS]:
            logging.error(f"Job with id {job_id} is not ready for analysis. Current status: {job.status}")
            return jsonify({"error": f"Job with id {job_id} is not ready for analysis. Current status: {job.status}"}), 400
            
        if not meeting.transcription:
            logging.error(f"Meeting with id {str(meeting.id)} is missing transcription data")
            return jsonify({"error": f"Meeting with id {str(meeting.id)} is missing transcription data"}), 400

        # Call Google RunCloud API for analysis
        buyer_id = str(meeting.buyer_id)
        meeting_id = str(meeting.id)
        
        # Get agency_id from the buyer
        buyer = meeting.buyer
        if not buyer:
            logging.error(f"Buyer not found for meeting {meeting_id}")
            return jsonify({"error": f"Buyer not found for meeting {meeting_id}"}), 404
        
        agency_id = str(buyer.agency_id)
        
        # Get RunCloud URL from environment variable or use default
        runcloud_url = os.getenv("RUNCLOUD_ANALYSIS_URL", "https://analysis-pipeline-staging-109365356440.europe-west1.run.app/analyze")
        logging.info(f"Using RunCloud URL: {runcloud_url}")
        
        try:
            # Add timeout and better error handling
            payload = {
                "buyer_id": buyer_id,
                "call_id": meeting_id,
                "agency_id": agency_id,
                "job_id": job_id
            }
            logging.info(f"Sending async request to RunCloud API with payload: {payload}")
            
            # Send request asynchronously - don't wait for response
            response = requests.post(
                runcloud_url, 
                json=payload,
                timeout=2,  # Shorter timeout to fire-and-forget
                verify=True,  # Verify SSL certificates
                stream=True  # Don't wait for full response
            )
            
            # Close the response immediately to free up resources
            response.close()
            
            logging.info(f"Successfully triggered async analysis via RunCloud API for job_id: {job_id} with agency_id: {agency_id}")
            logging.info(f"Request sent to RunCloud API - pipeline triggered")
        except requests.exceptions.Timeout as e:
            logging.error(f"Timeout calling RunCloud API for job_id {job_id}: {e}")
            return jsonify({"error": f"Timeout calling RunCloud API: {str(e)}"}), 504
        except requests.exceptions.SSLError as e:
            logging.error(f"SSL error calling RunCloud API for job_id {job_id}: {e}")
            return jsonify({"error": f"SSL error calling RunCloud API: {str(e)}"}), 502
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error calling RunCloud API for job_id {job_id}: {e}")
            return jsonify({"error": f"Connection error calling RunCloud API: {str(e)}"}), 503
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to call RunCloud API for job_id {job_id}: {e}")
            return jsonify({"error": f"Failed to trigger analysis via RunCloud API: {str(e)}"}), 500

        return jsonify({"message": f"Analysis task triggered successfully for job_id: {job_id}"}), 200
    except Exception as e:
        logging.error(f"Failed to trigger analysis for Job ID: {job_id} with error: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to trigger call analysis: {str(e)}"}), 500
