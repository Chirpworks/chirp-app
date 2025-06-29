import uuid

from sqlalchemy import UUID

from app import db


# Agency model
class Agency(db.Model):
    __tablename__ = 'agencies'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = db.Column(db.String(300), nullable=False)
    sellers = db.relationship('Seller', back_populates='agency', cascade='all, delete-orphan')
    buyers = db.relationship('Buyer', back_populates='agency', cascade='all, delete-orphan')
    products = db.relationship('Product', back_populates='agency', cascade='all, delete-orphan')
    description = db.Column(db.Text, nullable=True)

    def __init__(self, name):
        self.name = name
