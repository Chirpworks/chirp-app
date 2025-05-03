import logging
from flask import Blueprint, request, jsonify

from app import Job, Meeting
from app.service.call_analysis.call_analysis import CallAnalysis

logging = logging.getLogger(__name__)

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.route("/trigger_analysis", methods=["POST"])
def trigger_analysis():
    job_id = None
    try:
        logging.info(f"Triggering analysis")
        data = request.json
        job_id = data.get("job_id")
        logging.info(f"Processing analysis for Job ID: {job_id}")

        if not job_id:
            return jsonify({"error": "Missing job_id"}), 400

        job = Job.query().filter_by(id=job_id).first()
        if not job:
            logging.error(f"Job with id {job_id} not found")

        meeting = Meeting.query().filter_by(id=job.meeting_id).first()
        if not meeting:
            logging.error(f"Meeting for job {job_id} not found")
        if not meeting.diarization:
            logging.error(f"Meeting with id {meeting.id} is missing diarization data")

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
