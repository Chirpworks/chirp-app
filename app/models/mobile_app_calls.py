import uuid
from enum import Enum

from sqlalchemy import UUID

from app import db

from .user import User
from ..constants import CallDirection


# Deal model
class MobileAppCall(db.Model):
    __tablename__ = 'app_calls'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    mobile_app_call_id = db.Column(db.Integer, nullable=False)
    buyer_number = db.Column(db.String(15), nullable=False)
    seller_number = db.Column(db.String(15), nullable=False)
    call_type = db.Column(db.Enum(CallDirection), nullable=False)
    start_time = db.Column(db.DateTime, default=None, nullable=False)
    end_time = db.Column(db.DateTime, default=None, nullable=False)
    duration = db.Column(db.String(15), nullable=False)
