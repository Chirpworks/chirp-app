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
    key_discussion_points = db.Column(db.JSON, nullable=True)
    summary = db.Column(db.JSON, nullable=True)
    type = db.Column(db.JSON, nullable=True)
    detected_call_type = db.Column(db.JSON, nullable=True)
    detected_products = db.Column(db.JSON, nullable=True)
    qa_pairs = db.Column(db.JSON, nullable=True)
    facts = db.Column(db.JSON, nullable=True)

    actions = db.relationship('Action', back_populates='meeting', cascade='all, delete-orphan')
    call_performance = db.relationship('CallPerformance', back_populates='meeting', uselist=False, cascade='all, delete-orphan')
