import uuid
from enum import Enum

from sqlalchemy import UUID

from app import db

from .user import User


# Deal model
class MobileAppCall(db.Model):
    __tablename__ = 'app_calls'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    mobile_app_call_id = db.Column(db.Integer, nullable=False)
    buyer_number = db.Column(db.String(15), nullable=False)
    seller_number = db.Column(db.String(15), nullable=False)
    call_type = db.Column(db.String, nullable=True)
    start_time = db.Column(db.DateTime(timezone=True), default=None, nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), default=None, nullable=False)
    duration = db.Column(db.String(15), nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', back_populates='unmapped_app_calls')
    status = db.Column(db.String, nullable=False)
