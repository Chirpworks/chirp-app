import json
import os

import boto3

from app.constants import AWSConstants


def send_message_to_sqs():
    job_id = os.environ.get("JOB_ID")
    sqs_client = boto3.client('sqs', region_name=AWSConstants.AWS_REGION)
    message = {
        "job_id": job_id
    }
    response = sqs_client.send_message(
        QueueUrl=AWSConstants.DIARIZATION_REQUEST_QUEUE,
        MessageBody=json.dumps(message)
    )
    return response
