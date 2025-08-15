import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import UUID
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from pgvector.sqlalchemy import Vector


class SemanticDocument(db.Model):
    __tablename__ = 'semantic_documents'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    type = db.Column(db.String(64), nullable=False)
    text = db.Column(db.Text, nullable=False)
    meta = db.Column(JSONB, nullable=True)

    agency_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    meeting_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    buyer_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    product_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    seller_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)

    # embedding stored with pgvector; migration ensures extension and index
    embedding = db.Column(Vector(1536), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")), onupdate=datetime.now(ZoneInfo("Asia/Kolkata")), nullable=False)


