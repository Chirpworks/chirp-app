import uuid
from datetime import datetime

from sqlalchemy import UUID

from app import db


# Agency model
class Agency(db.Model):
    __tablename__ = 'agencies'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = db.Column(db.String(300), nullable=False)
    users = db.relationship('User', back_populates='agency', cascade='all, delete-orphan')
    products = db.Column(db.JSON, nullable=True)
    description = db.Column(db.String(300), nullable=True)

    def __init__(self, id, name):
        self.id = id
        self.name = name
