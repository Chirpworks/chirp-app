import os
from datetime import timedelta
import redis


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "default_secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", 'postgresql://chirp_user:chirp_password@localhost:5432/chirp_test')
    # SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", 'postgresql+psycopg2://postgres:cOdQDMWj<KUWr<lNs|<r>Ek)tX6u@chirp-db-dev.c1ayu2waec3w.ap-south-1.rds.amazonaws.com:5432/chirp-db-dev')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WHISPERX_TOKEN = os.getenv("WHISPERX_TOKEN", "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")

    JWT_SECRET_KEY = 'your_jwt_secret_key_here'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)  # Short lifespan for security
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    JWT_BLACKLIST_ENABLED = True  # Enable token blacklisting
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']  # Blacklist both token types

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

    # Flask-Session Config
    SESSION_TYPE = "redis"
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = "flask_session:"  # Prefix for session keys
    SESSION_REDIS = redis.Redis(host="localhost", port=6379, db=0)

    # celery config
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "db+sqlite:///results.sqlite"),
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "sqs://")
