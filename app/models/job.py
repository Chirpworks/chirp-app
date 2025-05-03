import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import UUID

from app import db

from .meeting import Meeting


class JobStatus(Enum):
    INIT = "init"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILURE = "failure"


class Job(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.Enum(JobStatus), default=JobStatus.INIT)
    s3_audio_url = db.Column(db.String(150), nullable=True, unique=True)
    meeting_id = db.Column(UUID(as_uuid=True), db.ForeignKey('meetings.id'), nullable=False, unique=True)
    # Relationship back to Meeting
    meeting = db.relationship('Meeting', back_populates='job')
