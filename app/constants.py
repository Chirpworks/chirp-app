from enum import Enum

import os


AGENT_MEETING_TIME_IN_HOURS = 1


class AWSConstants:
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION', 'ap-south-1')
    TOKEN_BUCKET_NAME = os.environ.get('TOKEN_BUCKET_NAME', 'tokens-dev')
    AGENT_ECS_CLUSTER_NAME = os.environ.get('AGENT_ECS_CLUSTER_NAME', "ecs_agent_running_dev")
    SPEAKER_DIARIZATION_ECS_CLUSTER_NAME = os.environ.get('SPEAKER_DIARIZATION_ECS_CLUSTER_NAME', "speaker_diarization_dev")
    ECS_AGENT_GOOGLE_TASK_DEFINITION = os.environ.get('ECS_AGENT_GOOGLE_TASK_DEFINITION', "google_meets_agent")
    SPEAKER_DIARIZATION_ECS_TASK_DEFINITION = os.environ.get('SPEAKER_DIARIZATION_ECS_TASK_DEFINITION', "speaker_diarization")
    SUBNETS = os.environ.get('SUBNETS', ["subnet-00e2fd531633923e5", "subnet-0cf22b7263dbb1cad", "subnet-0eca1542834cd7ac0"])  # VPC Subnets
    SECURITY_GROUPS = os.environ.get('SECURITY_GROUPS', ["sg-0ea1f9c2ac09b3c3d"])
    AUDIO_FILES_S3_BUCKET = os.environ.get('AUDIO_FILES_S3_BUCKET')
    DIARIZATION_REQUEST_QUEUE = os.environ.get('DIARIZATION_REQUEST_QUEUE', 'diarization_request_queue_dev')
    AWS_ACCOUNT_ID = os.environ.get('AWS_ACCOUNT_ID')
    SPEAKER_DIARIZATION_CONTAINER_NAME = os.environ.get('SPEAKER_DIARIZATION_CONTAINER_NAME', 'speaker_diarization')


class CalendarName(Enum):
    GOOGLE = 'google'


CALENDAR_NAME_TO_ECS_TASK_DEFINITION_MAP = {
    CalendarName.GOOGLE.value: AWSConstants.ECS_AGENT_GOOGLE_TASK_DEFINITION
}


CALENDAR_NAME_TO_ECS_CONTAINER_NAME_MAP = {
    CalendarName.GOOGLE.value: 'google-meets-agent'
}


class AgencyName(Enum):
    CHIRPWORKS = 'chirpworks'


AGENCY_NAME_TO_AGENCY_ID_MAPPING = {
    AgencyName.CHIRPWORKS.value: '1'
}
