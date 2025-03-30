from datetime import datetime

from app import db


# Agency model
class Agency(db.Model):
    __tablename__ = 'agencies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    users = db.relationship('User', back_populates='agency', cascade='all, delete-orphan')
