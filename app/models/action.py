import uuid
from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo

from sqlalchemy import UUID

from app import db


class ActionStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"


# Meeting model
class Action(db.Model):
    __tablename__ = 'actions'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    due_date = db.Column(db.DateTime(timezone=True), default=None, nullable=True)
    status = db.Column(db.Enum(ActionStatus), default=ActionStatus.PENDING, nullable=False)
    description = db.Column(db.JSON, nullable=True)
    reasoning = db.Column(db.Text, nullable=True)
    signals = db.Column(db.JSON, nullable=True)
    meeting_id = db.Column(UUID(as_uuid=True), db.ForeignKey('meetings.id'), nullable=False)
    meeting = db.relationship('Meeting', back_populates='actions')
    buyer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('buyers.id'), nullable=False)
    buyer = db.relationship('Buyer', back_populates='actions')
    seller_id = db.Column(UUID(as_uuid=True), db.ForeignKey('sellers.id'), nullable=False)
    seller = db.relationship('Seller', back_populates='actions')
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")), nullable=True)
