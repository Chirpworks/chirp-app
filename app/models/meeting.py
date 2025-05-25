import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import UUID

from app import db

from .user import User
from ..constants import MeetingSource


class ProcessingStatus(Enum):
    INITIALIZED = "initialized"
    PROCESSING = "processing"
    COMPLETE = "complete"


# Meeting model
class Meeting(db.Model):
    __tablename__ = 'meetings'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    mobile_app_call_id = db.Column(db.Integer, nullable=True)
    buyer_number = db.Column(db.String(15), nullable=False)
    seller_number = db.Column(db.String(15), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    scheduled_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.Enum(ProcessingStatus), default=ProcessingStatus.PROCESSING)
    source = db.Column(db.Enum(MeetingSource), nullable=False)
    participants = db.Column(db.JSON, nullable=True)
    start_time = db.Column(db.DateTime, default=datetime.now())
    end_time = db.Column(db.DateTime, default=datetime.utcnow)
    summary = db.Column(db.JSON, nullable=True)
    transcription = db.Column(db.Text, nullable=True)
    diarization = db.Column(db.Text, nullable=True)
    call_notes = db.Column(db.JSON, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    job = db.relationship('Job', back_populates='meeting', uselist=False, cascade='all, delete-orphan')
    actions = db.relationship('Action', back_populates='meeting', cascade='all, delete-orphan')
    deal_id = db.Column(UUID(as_uuid=True), db.ForeignKey('deals.id'), nullable=True)
    deal = db.relationship('Deal', back_populates='meetings')
    direction = db.Column(db.String, nullable=True)
