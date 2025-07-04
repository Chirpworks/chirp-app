import os
import json
import boto3

# Initialize the ECS client using Boto3
ecs_client = boto3.client('ecs', region_name=os.environ['AWS_REGION_NAME'])


def lambda_handler(event, context):
    """
    Lambda function that is triggered by SQS events.
    It reads each message, extracts job data, and calls ECS run_task to dispatch the job.
    """
    results = []
    for record in event.get('Records', []):
        try:
            # SQS message body is expected to be JSON
            message_body = json.loads(record['body'])
            job_id = message_body.get('job_id')

            if not job_id:
                raise ValueError("Message missing required field 'job_id'.")

            # Build the ECS task overrides
            overrides = {
                "containerOverrides": [
                    {
                        "name": "whisperx-container",  # Must match container name in your task definition
                        "environment": [
                            {"name": "JOB_ID", "value": job_id},
                        ]
                    }
                ]
            }

            response = ecs_client.run_task(
                cluster=os.environ['SPEAKER_DIARIZATION_ECS_CLUSTER_NAME'],
                taskDefinition=os.environ['SPEAKER_DIARIZATION_ECS_TASK_DEFINITION'],
                launchType='FARGATE',
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": os.environ['SUBNETS'].split(','),
                        "securityGroups": os.environ['SECURITY_GROUPS'].split(','),
                        "assignPublicIp": "ENABLED"
                    }
                },
                overrides=overrides
            )

            # Log the response for debugging
            results.append({
                "job_id": job_id,
                "response": response
            })
            print(f"Launched ECS task for job {job_id}: {response}")
        except Exception as e:
            print(f"Error processing record: {e}")
            # Optionally, you might want to send the message to a dead-letter queue
            results.append({"error": str(e)})
    return {
        "statusCode": 200,
        "body": json.dumps(results)
    }
