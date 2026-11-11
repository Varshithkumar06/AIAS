"""
AIAS Configuration Module
Loads environment variables and provides app-wide settings.
"""

import os
import secrets
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Determine environment
flask_env = os.getenv("FLASK_ENV", "production")

# Required for local OAuth over HTTP (not HTTPS)
if flask_env == "development":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
    FLASK_ENV = os.getenv("FLASK_ENV", "production")

    # MongoDB Database
    MONGO_URI = os.getenv(
        "MONGO_URI",
        "mongodb+srv://AIAS_service:Kaliuser%4012345@clusteraias1.nrpbm9n.mongodb.net/aias_db?retryWrites=true&w=majority&appName=Clusteraias1"
    )

    # Email (Gmail SMTP)
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_SENDER_NAME = "AIAS Security"

    # OTP Settings
    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = 5
    OTP_MAX_ATTEMPTS = 5

    # ── Database Reliability ──
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "30"))
    DB_MAX_RETRIES = int(os.getenv("DB_MAX_RETRIES", "3"))
    DB_RETRY_BACKOFF_BASE = float(os.getenv("DB_RETRY_BACKOFF_BASE", "1.0"))

    # Rate Limiting & Redis
    MAX_OTP_REQUESTS_PER_HOUR = 5
    LOCKOUT_DURATION_MINUTES = 15
    MAX_FAILED_LOGINS = 5
    GLOBAL_RATE_LIMIT_LIMIT = int(os.getenv("GLOBAL_RATE_LIMIT_LIMIT", "100"))
    GLOBAL_RATE_LIMIT_WINDOW = int(os.getenv("GLOBAL_RATE_LIMIT_WINDOW", "60"))
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ── Redis Reliability ──
    REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
    REDIS_SOCKET_TIMEOUT = int(os.getenv("REDIS_SOCKET_TIMEOUT", "1"))
    REDIS_CIRCUIT_BREAKER_COOLDOWN = int(os.getenv("REDIS_CIRCUIT_BREAKER_COOLDOWN", "30"))

    # Session
    SESSION_LIFETIME_HOURS = 24
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds

    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/auth/google/callback")

    # Zoom API Settings
    ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID", "")
    ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID", "")
    ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET", "")


    # Security Headers
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = flask_env != "development"
