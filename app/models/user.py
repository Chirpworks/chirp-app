from app import db
from flask_login import UserMixin

from enum import Enum

from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token

from .agency import Agency


class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole)
    agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'), nullable=False)
    agency = db.relationship('Agency', back_populates='users')
    meetings = db.relationship('Meeting', back_populates='user', cascade='all, delete-orphan')
    last_week_performance_analysis = db.Column(db.String(), nullable=True)

    def __init__(self, username, email, password, agency_id):
        self.username = username
        self.email = email
        self.set_password(password)
        self.agency_id = agency_id

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_access_token(self, **kwargs):
        return create_access_token(identity=self.id, **kwargs)

    def generate_refresh_token(self):
        return create_refresh_token(identity=self.id)
