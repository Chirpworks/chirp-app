from enum import Enum

import os

AGENT_MEETING_TIME_IN_HOURS = 1

FLASK_API_URL = os.environ.get("FLASK_API_URL")

class AWSConstants:
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION', 'ap-south-1')
    TOKEN_BUCKET_NAME = os.environ.get('TOKEN_BUCKET_NAME', 'tokens-dev')
    AGENT_ECS_CLUSTER_NAME = os.environ.get('AGENT_ECS_CLUSTER_NAME', "ecs_agent_running_dev")
    SPEAKER_DIARIZATION_ECS_CLUSTER_NAME = os.environ.get('SPEAKER_DIARIZATION_ECS_CLUSTER_NAME', "speaker_diarization")
    SPEAKER_DIARIZATION_CPU_ECS_CLUSTER_NAME = os.environ.get('SPEAKER_DIARIZATION_ECS_CLUSTER_NAME',
                                                          "speaker_diarization_cpu")
    ECS_AGENT_GOOGLE_TASK_DEFINITION = os.environ.get('ECS_AGENT_GOOGLE_TASK_DEFINITION', "google_meets_agent")
    SPEAKER_DIARIZATION_ECS_TASK_DEFINITION = os.environ.get('SPEAKER_DIARIZATION_ECS_TASK_DEFINITION', "speaker-diarization")
    CALL_ANALYSIS_ECS_TASK_DEFINITION = os.environ.get("CALL_ANALYSIS_ECS_TASK_DEFINITION", "call-analysis")
    CALL_ANALYSIS_CONTAINER_NAME = os.environ.get("CALL_ANALYSIS_CONTAINER_NAME", "call-analysis")
    CALL_ANALYSIS_CLUSTER_NAME = os.environ.get("CALL_ANALYSIS_CLUSTER_NAME", "call-analysis")
    SUBNETS = os.environ.get('SUBNETS', ["subnet-00e2fd531633923e5", "subnet-0cf22b7263dbb1cad", "subnet-0eca1542834cd7ac0"])  # VPC Subnets
    SECURITY_GROUPS = os.environ.get('SECURITY_GROUPS', ["sg-0ea1f9c2ac09b3c3d", "sg-0856da2128f0445a8"])
    AUDIO_FILES_S3_BUCKET = os.environ.get('AUDIO_FILES_S3_BUCKET', "chirp-call-recordings")
    DIARIZATION_REQUEST_QUEUE = os.environ.get('DIARIZATION_REQUEST_QUEUE', 'diarization_request_queue_dev')
    AWS_ACCOUNT_ID = os.environ.get('AWS_ACCOUNT_ID')
    SPEAKER_DIARIZATION_CONTAINER_NAME = os.environ.get('SPEAKER_DIARIZATION_CONTAINER_NAME', 'speaker-diarization')
    SMTP_SERVER = 'email-smtp.ap-south-1.amazonaws.com'
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    SMTP_PORT = 465


class ExotelCreds:
    EXOTEL_API_KEY = os.environ.get('EXOTEL_API_KEY')
    EXOTEL_API_TOKEN = os.environ.get('EXOTEL_API_TOKEN')


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


class MeetingSource(Enum):
    PHONE = "phone"
    VIDEO_CALL = "video_call"
    GOOGLE_MEETS = "google_meets"


class CallDirection(Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    MISSED = "missed"
