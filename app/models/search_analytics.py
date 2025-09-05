import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import UUID

from app import db


class SearchAnalytics(db.Model):
    """
    Model for tracking search queries and performance analytics.
    """
    __tablename__ = 'search_analytics'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('sellers.id'), nullable=False)
    agency_id = db.Column(UUID(as_uuid=True), db.ForeignKey('agencies.id'), nullable=False)
    query = db.Column(db.String(255), nullable=False)
    results_count = db.Column(db.Integer, nullable=False)
    search_time_ms = db.Column(db.Integer, nullable=False)
    cached = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")), nullable=False)
    
    # Relationships
    user = db.relationship('Seller', backref='search_analytics')
    agency = db.relationship('Agency', backref='search_analytics')
    
    def __init__(self, user_id, agency_id, query, results_count, search_time_ms, cached=False):
        self.user_id = user_id
        self.agency_id = agency_id
        self.query = query
        self.results_count = results_count
        self.search_time_ms = search_time_ms
        self.cached = cached
