import os
import logging
import runpod
import traceback

# Your diarization function
from service.transcription.speaker_diarization_linux import run_diarization

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define handler
def handler(event):
    logger.info(f"Received event: {event}")
    try:
        job_id = event.get("input").get("job_id")
        if not job_id:
            raise ValueError("Missing 'job_id' in event payload.")
        os.environ["JOB_ID"] = job_id
        logger.info(f"Set JOB_ID: {job_id}")
        run_diarization(job_id)
        return {"status": "success", "job_id": job_id}
    except Exception as e:
        logger.error("Exception occurred in handler:")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}

# 🟡 This keeps the worker alive for RunPod Serverless
runpod.serverless.start({"handler": handler})