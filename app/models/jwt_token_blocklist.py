from app import db


class TokenBlocklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True)  # Unique Token ID
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
