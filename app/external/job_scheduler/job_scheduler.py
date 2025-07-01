from datetime import datetime, timezone

from app.external.aws.ecs_client import ECSClient
from app.constants import CalendarName


class JobScheduler:
    def __init__(self):
        self.ecs_client = ECSClient()

    # def schedule_agent_job(self, event: dict, calendar_name: CalendarName):
    #     start_time_str = event['start']['dateTime']
    #     if start_time_str:
    #         start_time = datetime.fromisoformat(start_time_str).replace(tzinfo=timezone.utc)
    #     else:
    #         start_time = datetime.now(timezone.utc)
    #
    #     job_id = event['job_id']
    #
    #     # Schedule the job
    #     scheduler.add_job(
    #         self.ecs_client.run_agent_task,
    #         "date",
    #         run_date=start_time,
    #         args=[job_id, calendar_name],
    #         id=str(job_id),
    #         replace_existing=True
    #     )
    #     print(f"Job {job_id} scheduled for {start_time}")
