from datetime import datetime
from enum import Enum

from app import db

from .user import User


class MeetingStatus(Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"


# Meeting model
class Meeting(db.Model):
    __tablename__ = 'meetings'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    scheduled_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', back_populates='meetings')
    status = db.Column(db.Enum(MeetingStatus), default=MeetingStatus.SCHEDULED)
    transcription = db.Column(db.Text, nullable=True)
    analysis = db.Column(db.Text, nullable=True)
    job = db.relationship('Job', back_populates='meeting', uselist=False, cascade='all, delete-orphan')
