import logging
import os

import runpod

from service.transcription.speaker_diarization_linux import run_diarization

logger = logging.getLogger(__name__)


def handler(event):
    try:
        logger.info(f"Received event: {event}")
        job_id = event.get("input").get("job_id")
        logger.info(f"Job ID: {job_id}")
        if not job_id:
            logger.info("missing job_id")
            result = {"status": "error", "summary": "job_id param missing"}
        else:
            # Run diarization on audio_url
            os.environ['JOB_ID'] = job_id
            run_diarization(job_id)
            result = {"status": "success", "summary": "diarization done"}
        return result
    except Exception as e:
        result = {"status": "error", "summary": f"{e}"}
        return result


runpod.serverless.start({"handler": handler})
