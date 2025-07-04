import os

import boto3
import json

from app.constants import AWSConstants
from app.external.aws.sqs_client import SQSClient


# Initialize AWS clients
ecs_client = boto3.client("ecs", region_name=AWSConstants.AWS_REGION)


# TODO: implement the details in this class
def process_queue():
    sqs_client = SQSClient(os.environ.get('QUEUE_URL'))
    while True:
        # Poll SQS for messages
        response = sqs_client.receive_message()

        if "Messages" in response:
            for message in response["Messages"]:
                try:
                    # Parse message
                    body = json.loads(message["Body"].replace("'", '"'))  # Handle single quotes
                    job_id = body["job_id"]
                    job_data = body["job_data"]

                    # Launch ECS task
                    ecs_client.run_task(
                        cluster=AWSConstants.AGENT_ECS_CLUSTER_NAME,
                        launchType="FARGATE",
                        taskDefinition=AWSConstants.TASK_DEFINITION,
                        networkConfiguration={
                            "awsvpcConfiguration": {
                                "subnets": AWSConstants.SUBNETS,
                                "securityGroups": AWSConstants.SECURITY_GROUPS,
                                "assignPublicIp": "ENABLED"
                            }
                        },
                        overrides={
                            "containerOverrides": [
                                {
                                    "name": "your-container-name",
                                    "environment": [
                                        {"name": "JOB_ID", "value": job_id},
                                        {"name": "JOB_DATA", "value": json.dumps(job_data)}
                                    ]
                                }
                            ]
                        }
                    )

                    # Delete message from queue after processing
                    sqs_client.delete_message(
                        receipt_handle=message["ReceiptHandle"]
                    )
                    print(f"Job {job_id} processed and ECS task launched.")
                except Exception as e:
                    print(f"Error processing message: {e}")
