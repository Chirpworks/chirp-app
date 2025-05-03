import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")


def process_diarization(job_id):
    from app.models.job import Job
    from app import db

    # Fetch transcription from DB
    job = Job.query.get(job_id)
    if not job or not job.transcription_text:
        return {"status": "error", "message": "No transcription found"}

    try:
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": job.transcription_text}]
        )

        # Store result in DB
        job.analysis_data = response["choices"][0]["message"]["content"]
        db.session.commit()

        return {"status": "success", "job_id": job_id}

    except Exception as e:
        return {"status": "error", "message": str(e)}
