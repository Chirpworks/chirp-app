import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import ENUM


from sqlalchemy import UUID

from app import db

from .user import User

IST = timezone(timedelta(hours=5, minutes=30))


class ActionStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class ActionType(Enum):
    SUGGESTED_ACTION = "suggested_action"
    CONTEXTUAL_ACTION = "contextual_action"


# Meeting model
class Action(db.Model):
    __tablename__ = 'actions'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    due_date = db.Column(db.DateTime(timezone=True), default=None, nullable=True)
    status = db.Column(db.Enum(ActionStatus), default=ActionStatus.PENDING, nullable=False)
    type = db.Column(ENUM(ActionType, name="actiontype", values_callable=lambda x: [e.value for e in x]), default=ActionType.CONTEXTUAL_ACTION, nullable=True)
    description = db.Column(db.JSON, nullable=True)
    reasoning = db.Column(db.Text, nullable=True)
    signals = db.Column(db.JSON, nullable=True)
    meeting_id = db.Column(UUID(as_uuid=True), db.ForeignKey('meetings.id'), nullable=False)
    meeting = db.relationship('Meeting', back_populates='actions')
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")), nullable=True)
