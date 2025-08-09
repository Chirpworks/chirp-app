import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import UUID

from app import db


class CallPerformance(db.Model):
    __tablename__ = 'call_performances'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    meeting_id = db.Column(UUID(as_uuid=True), db.ForeignKey('meetings.id'), nullable=False, unique=True)
    meeting = db.relationship('Meeting', back_populates='call_performance')
    
    # Performance metrics - each stored as JSON with structure:
    # {"date": "2024-01-15", "score": 8.5, "reason": "Excellent introduction with clear value proposition"}
    intro = db.Column(db.JSON, nullable=True)
    rapport_building = db.Column(db.JSON, nullable=True)
    need_realization = db.Column(db.JSON, nullable=True)
    script_adherance = db.Column(db.JSON, nullable=True)
    objection_handling = db.Column(db.JSON, nullable=True)
    pricing_and_negotiation = db.Column(db.JSON, nullable=True)
    closure_and_next_steps = db.Column(db.JSON, nullable=True)
    conversation_structure_and_flow = db.Column(db.JSON, nullable=True)
    
    # Overall performance score (can be calculated from individual metrics)
    overall_score = db.Column(db.Float, nullable=True)
    
    # Metadata
    analyzed_at = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Kolkata")), onupdate=datetime.now(ZoneInfo("Asia/Kolkata")), nullable=False)
    
    def __init__(self, meeting_id, **kwargs):
        self.meeting_id = meeting_id
        
        # Initialize metrics with provided data
        self.intro = kwargs.get('intro')
        self.rapport_building = kwargs.get('rapport_building')
        self.need_realization = kwargs.get('need_realization')
        self.script_adherance = kwargs.get('script_adherance')
        self.objection_handling = kwargs.get('objection_handling')
        self.pricing_and_negotiation = kwargs.get('pricing_and_negotiation')
        self.closure_and_next_steps = kwargs.get('closure_and_next_steps')
        self.conversation_structure_and_flow = kwargs.get('conversation_structure_and_flow')
        self.overall_score = kwargs.get('overall_score')
        
        if kwargs.get('analyzed_at'):
            self.analyzed_at = kwargs.get('analyzed_at')
    
    def calculate_overall_score(self):
        """Calculate overall score from individual metrics"""
        scores = []
        metrics = [
            self.intro, self.rapport_building, self.need_realization,
            self.script_adherance, self.objection_handling, 
            self.pricing_and_negotiation, self.closure_and_next_steps,
            self.conversation_structure_and_flow
        ]
        
        for metric in metrics:
            if metric and isinstance(metric, dict) and 'score' in metric:
                try:
                    scores.append(float(metric['score']))
                except (ValueError, TypeError):
                    continue
        
        if scores:
            self.overall_score = sum(scores) / len(scores)
        
        return self.overall_score
    
    @staticmethod
    def get_metric_names():
        """Get list of all performance metric names"""
        return [
            'intro', 'rapport_building', 'need_realization',
            'script_adherance', 'objection_handling', 
            'pricing_and_negotiation', 'closure_and_next_steps',
            'conversation_structure_and_flow'
        ] 