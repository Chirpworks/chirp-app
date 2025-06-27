import uuid

from sqlalchemy import UUID

from app import db
from flask_login import UserMixin

from enum import Enum

from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token

from .agency import Agency


class SellerRole(Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    GUEST = "guest"


class Seller(db.Model, UserMixin):
    __tablename__ = 'sellers'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(150), nullable=True, unique=True)
    name = db.Column(db.String(100), nullable=False, unique=False)
    email = db.Column(db.String(150), nullable=False, unique=True)
    phone = db.Column(db.String(20), nullable=False, unique=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.Enum(SellerRole), default=SellerRole.USER)
    agency_id = db.Column(UUID(as_uuid=True), db.ForeignKey('agencies.id'), nullable=False)
    agency = db.relationship('Agency', back_populates='sellers')
    calls = db.relationship('Meeting', back_populates='seller', cascade='all, delete-orphan')
    unmapped_app_calls = db.relationship('MobileAppCall', back_populates='user', cascade='all, delete-orphan')
    manager_id = db.Column(UUID(as_uuid=True), db.ForeignKey('sellers.id'), nullable=True)
    manager = db.relationship('Seller', remote_side=[id], backref='team_members')

    def __init__(self, email, phone, password, agency_id, name, role=None):
        self.email = email
        self.set_password(password)
        self.agency_id = agency_id
        self.role = SellerRole(role) if role else SellerRole.USER
        self.name = name
        self.phone = phone

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_access_token(self, **kwargs):
        return create_access_token(identity=self.id, **kwargs)

    def generate_refresh_token(self):
        return create_refresh_token(identity=self.id)
