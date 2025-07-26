import uuid
from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo

from sqlalchemy import UUID

from app import db

from ..constants import MeetingSource


class ProcessingStatus(Enum):
    INITIALIZED = "initialized"
    PROCESSING = "processing"
    COMPLETE = "complete"


# Meeting model
class Meeting(db.Model):
    __tablename__ = 'meetings'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    mobile_app_call_id = db.Column(db.String(50), nullable=True)
    buyer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('buyers.id'), nullable=False)
    buyer = db.relationship('Buyer', back_populates='meetings')
    seller_id = db.Column(UUID(as_uuid=True), db.ForeignKey('sellers.id'), nullable=False)
    seller = db.relationship('Seller', back_populates='meetings')
    source = db.Column(db.Enum(MeetingSource), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")))
    end_time = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")))
    transcription = db.Column(db.Text, nullable=True)
    direction = db.Column(db.String, nullable=True)
    job = db.relationship('Job', back_populates='meeting', uselist=False, cascade='all, delete-orphan')

    # following fields populated by LLM
    title = db.Column(db.String(300), nullable=False)
    call_purpose = db.Column(db.String, nullable=True)
    key_discussion_points = db.Column(db.JSON, nullable=True)
    buyer_pain_points = db.Column(db.JSON, nullable=True)
    solutions_discussed = db.Column(db.JSON, nullable=True)
    risks = db.Column(db.JSON, nullable=True)
    summary = db.Column(db.JSON, nullable=True)
    type = db.Column(db.JSON, nullable=True)

    actions = db.relationship('Action', back_populates='meeting', cascade='all, delete-orphan')
    call_performance = db.relationship('CallPerformance', back_populates='meeting', uselist=False, cascade='all, delete-orphan')
