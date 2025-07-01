import logging
from flask import Blueprint, request, jsonify

from app.external.call_analysis.call_analysis import CallAnalysis
from app.services import JobService, MeetingService

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
        if not meeting.diarization:
            logging.error(f"Meeting with id {meeting.id} is missing diarization data")
            return jsonify({"error": f"Meeting with id {meeting.id} is missing diarization data"}), 400

        call_analyzer = CallAnalysis(meeting=meeting)
        call_analyzer.analyze_meeting()

        # logging.info("Initializing ECS task for diarization.")
        # # Initialize ECS task for speaker diarization
        # ecs_client = ECSClient()
        # task_response = ecs_client.run_analysis_task(job_id=job_id)

        return jsonify({"message": f"Analysis task completed successfully for job_id: {job_id}"}), 200
    except Exception as e:
        logging.error(f"Failed to trigger analysis for Job ID: {job_id} with error: {e}")
        return jsonify({"error": f"Failed to trigger call analysis: {str(e)}"}), 500
