import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import UUID

from app import db


# Deal model
class ExotelCall(db.Model):
    __tablename__ = 'exotel_calls'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    call_from = db.Column(db.String(15), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")), nullable=False)
    duration = db.Column(db.Integer, nullable=False, default=0)
    end_time = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")), nullable=False)
    call_recording_url = db.Column(db.Text, nullable=True)
