import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import UUID

from app import db


# Deal model
class MobileAppCall(db.Model):
    __tablename__ = 'app_calls'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    mobile_app_call_id = db.Column(db.String(50), nullable=False)
    buyer_number = db.Column(db.String(15), nullable=False)
    seller_number = db.Column(db.String(15), nullable=False)
    call_type = db.Column(db.String, nullable=True)
    start_time = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")), nullable=False)
    duration = db.Column(db.Integer, nullable=False, default=0)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('sellers.id'), nullable=False)
    user = db.relationship('Seller', back_populates='unmapped_app_calls')
    status = db.Column(db.String, nullable=False)
