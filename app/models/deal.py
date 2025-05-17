import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import UUID
from sqlalchemy.dialects.postgresql import ENUM

from app import db

from .user import User


class DealStatus(Enum):
    OPEN = "open"
    SUCCESS = "success"
    FAILURE = "failure"


# Deal model
class Deal(db.Model):
    __tablename__ = 'deals'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = db.Column(db.String(300), nullable=False)
    stage = db.Column(db.String(100), default=None, nullable=True)
    stage_signals = db.Column(db.JSON, nullable=True)
    stage_reasoning = db.Column(db.JSON, nullable=True)
    focus_areas = db.Column(db.JSON, nullable=True)
    risks = db.Column(db.JSON, nullable=True)
    lead_qualification = db.Column(db.JSON, nullable=True)
    overview = db.Column(db.JSON, nullable=True)
    key_stakeholders = db.Column(db.JSON, nullable=True)
    buyer_number = db.Column(db.String(15), nullable=False)
    seller_number = db.Column(db.String(15), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    pain_points = db.Column(db.JSON, nullable=True)
    solutions = db.Column(db.JSON, nullable=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', back_populates='deals')
    meetings = db.relationship('Meeting', back_populates='deal', cascade='all, delete-orphan')
    history = db.Column(db.JSON, nullable=True)
    status = db.Column(ENUM(DealStatus, name="dealstatus", values_callable=lambda x: [e.value for e in x]), default=DealStatus.OPEN, nullable=True)
