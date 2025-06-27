import uuid
from sqlalchemy import UUID
from app import db


# Product model
class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    agency_id = db.Column(UUID(as_uuid=True), db.ForeignKey('agencies.id'), nullable=False)
    agency = db.relationship('Agency', back_populates='products')
    name = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    features = db.Column(db.JSON, nullable=True)
