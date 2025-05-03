import uuid

from sqlalchemy import UUID

from app import db


class TokenBlocklist(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    jti = db.Column(db.String(36), nullable=False, index=True)  # Unique Token ID
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
