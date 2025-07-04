import os
import time
from datetime import datetime, timedelta
import logging

import boto3
from flask import Flask

from app import Job, db
from app.constants import AWSConstants, CALENDAR_NAME_TO_ECS_TASK_DEFINITION_MAP, CalendarName, \
    AGENT_MEETING_TIME_IN_HOURS, CALENDAR_NAME_TO_ECS_CONTAINER_NAME_MAP
from app.models.job import JobStatus

logging = logging.getLogger(__name__)


class ECSClient:
    def __init__(self):
        """Initialize the ECS client with required configurations."""
        self.region = AWSConstants.AWS_REGION
        self.agent_cluster_name = AWSConstants.AGENT_ECS_CLUSTER_NAME
        self.speaker_diarization_cluster_name = AWSConstants.SPEAKER_DIARIZATION_ECS_CLUSTER_NAME
        self.speaker_diarization_cpu_cluster_name = AWSConstants.SPEAKER_DIARIZATION_CPU_ECS_CLUSTER_NAME
        self.subnets = AWSConstants.SUBNETS
        self.security_groups = AWSConstants.SECURITY_GROUPS

        self.client = boto3.client("ecs", region_name=self.region)

    def run_agent_task(self, job_id: str, calendar_name: CalendarName):
        """Run a job on ECS."""
        task_definition = CALENDAR_NAME_TO_ECS_TASK_DEFINITION_MAP.get(calendar_name.value)
        container_name = CALENDAR_NAME_TO_ECS_CONTAINER_NAME_MAP.get(calendar_name.value)
        
        if not task_definition or not container_name:
            raise ValueError(f"No task definition or container name found for calendar: {calendar_name.value}")
        
        # TODO: Add env vars for email = os.getenv("GOOGLE_AGENT_EMAIL")
        #     password = os.getenv("GOOGLE_AGENT_PASSWORD")
        #     meet_link = os.getenv("GOOGLE_MEET_LINK") as overrides here
        return self.run_task(task_definition=task_definition, container_name=container_name, job_id=job_id, cluster_name=self.agent_cluster_name)

    def get_agent_task_status(self, job_id):
        """Fetch ECS task status using job_id."""
        job = Job.query.get(job_id)
        if not job:
            return None

        # Get list of tasks
        response = self.client.list_tasks(cluster=self.agent_cluster_name)
        tasks = response.get("taskArns", [])

        for task_arn in tasks:
            task_info = self.client.describe_tasks(cluster=self.agent_cluster_name, tasks=[task_arn])
            task = task_info.get("tasks", [])[0]

            # Extract Job ID from environment variables inside the container
            container = task.get("containers", [])[0]
            env_vars = container.get("environment", [])
            ecs_job_id = next((env["value"] for env in env_vars if env["name"] == "JOB_ID"), None)

            if ecs_job_id == job_id:
                return task

        return None

    def monitor_agent_jobs(self, app: Flask):
        """Continuously monitor job statuses and update the database."""
        with app.app_context():
            while True:
                running_jobs = Job.query.filter_by(status="running").all()

                for job in running_jobs:
                    task = self.get_agent_task_status(job.id)

                    if not task:
                        continue  # Skip if task not found

                    last_status = task["lastStatus"]
                    exit_code = task.get("containers", [{}])[0].get("exitCode", 0)

                    # Check for failure scenarios
                    if last_status == "STOPPED" and exit_code != 0:
                        job.status = JobStatus.FAILURE
                        job.completed_at = datetime.utcnow()
                        db.session.commit()
                        print(f"Job {job.id} marked as FAILED (Exit Code: {exit_code})")

                    elif last_status in ["FAILED", "DEACTIVATING"]:
                        job.status = JobStatus.FAILURE
                        job.completed_at = datetime.utcnow()
                        db.session.commit()
                        print(f"Job {job.id} marked as FAILED due to ECS failure status.")

                    # Check for timeout (e.g., 1-hour runtime exceeded)
                    elif job.started_at and datetime.utcnow() - job.started_at > timedelta(hours=AGENT_MEETING_TIME_IN_HOURS):
                        job.status = JobStatus.FAILURE
                        job.completed_at = datetime.utcnow()
                        db.session.commit()
                        print(f"Job {job.id} marked as FAILED due to timeout.")

                    # Mark job as completed if it finishes successfully
                    elif last_status == "STOPPED" and exit_code == 0:
                        job.status = JobStatus.COMPLETED
                        job.completed_at = datetime.utcnow()
                        db.session.commit()
                        print(f"Job {job.id} marked as COMPLETED.")

                time.sleep(60)  # Check every 60 seconds

    def run_analysis_task(self, job_id: str):
        """Run analysis task on ECS for fetching data via LLM"""
        try:
            logging.info(f"Starting analysis on ECS for job_id: {job_id}")
            task_definition = AWSConstants.CALL_ANALYSIS_ECS_TASK_DEFINITION
            container_name = AWSConstants.CALL_ANALYSIS_CONTAINER_NAME
            return self.run_task(
                task_definition=task_definition,
                container_name=container_name,
                job_id=job_id,
                cluster_name=AWSConstants.CALL_ANALYSIS_CLUSTER_NAME
            )
        except Exception as e:
            logging.error(f"Failed to run call analysis task on ECS for job id: {job_id} with error: {e}")
            raise e

    def run_speaker_diarization_task(self, job_id: str):
        """Run a diarization job on ECS."""
        try:
            logging.info(f"Starting diarization task on ECS for job_id: {job_id}")
            task_definition = AWSConstants.SPEAKER_DIARIZATION_ECS_TASK_DEFINITION
            container_name = AWSConstants.SPEAKER_DIARIZATION_CONTAINER_NAME
            return self.run_task(
                task_definition=task_definition,
                container_name=container_name,
                job_id=job_id,
                cluster_name=self.speaker_diarization_cpu_cluster_name
            )
        except Exception as e:
            logging.error(f"Failed to run diarization task on ECS for job id: {job_id} with error: {e}")
            raise e

    def run_task(self, task_definition: str, container_name: str, job_id: str, cluster_name: str):
        try:
            response = self.client.run_task(
                cluster=cluster_name,
                taskDefinition=task_definition,
                launchType="FARGATE",
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": self.subnets,
                        "securityGroups": self.security_groups,
                        "assignPublicIp": "ENABLED"
                    }
                },
                overrides={
                    "containerOverrides": [
                        {
                            "name": container_name,
                            "environment": [
                                {"name": "JOB_ID", "value": str(job_id)},
                                {"name": "FLASK_API_URL", "value": os.environ["FLASK_API_URL"]},
                                {"name": "DATABASE_URL", "value": os.environ["DATABASE_URL"]}
                            ]
                        }
                    ]
                },
            )
            logging.info(f"ECS Task Started for Job ID {job_id}: {response}")
            return response
        except Exception as e:
            logging.error(f"Failed to start diarization ECS task for job_id: {job_id} with error {str(e)}")
            raise e
