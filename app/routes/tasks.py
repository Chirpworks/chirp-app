# from flask import Blueprint, request, jsonify
# from app.celery_tasks.diarization_task import process_diarization
#
# task_bp = Blueprint("task", __name__)
#
#
# @task_bp.route("/trigger_analysis", methods=["POST"])
# def trigger_analysis():
#     data = request.json
#     job_id = data.get("job_id")
#
#     if not job_id:
#         return jsonify({"error": "Missing job_id"}), 400
#
#     task = process_diarization.apply_async(args=[job_id])
#     return jsonify({"task_id": task.id, "status": "processing"})
