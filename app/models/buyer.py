import uuid

from sqlalchemy import UUID

from app import db


class Buyer(db.Model):
    __tablename__ = 'buyers'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = db.Column(db.String(20), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    agency_id = db.Column(UUID(as_uuid=True), db.ForeignKey('agencies.id'), nullable=False)
    agency = db.relationship('Agency', back_populates='buyers')
    meetings = db.relationship('Meeting', back_populates='buyer', cascade='all, delete-orphan')
    actions = db.relationship('Action', back_populates='buyer', cascade='all, delete-orphan')
    tags = db.Column(db.JSON, nullable=True)
    requirements = db.Column(db.JSON, nullable=True)
    solutions_presented = db.Column(db.JSON, nullable=True)
    relationship_progression = db.Column(db.Text, nullable=True)
    risks = db.Column(db.JSON, nullable=True)
    products_discussed = db.Column(db.JSON, nullable=True)
    company_name = db.Column(db.String(100), nullable=True)
