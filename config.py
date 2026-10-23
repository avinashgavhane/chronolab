"""
ChronoLab - Production Configuration Module
============================================
Handles environment-specific configurations:
- DevelopmentConfig (local SQLite, debug mode)
- ProductionConfig (PostgreSQL/SQLite, secure cookies, CSRF protection, strict logging)
- TestingConfig (in-memory SQLite, isolated test suite)
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base Configuration with enterprise security defaults."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "chronolab-enterprise-vault-secret-key-prod-2026")
    
    # Database Settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Maximum file upload size: 16 Megabytes (prevents Denial of Service via large files)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # Directory paths
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    REPORTS_FOLDER = os.path.join(UPLOAD_FOLDER, "reports")
    SNIPPETS_FOLDER = os.path.join(UPLOAD_FOLDER, "snippets")
    
    # Session & Cookie Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)


class DevelopmentConfig(Config):
    """Local development setup with hot reload."""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", 
        f"sqlite:///{os.path.join(BASE_DIR, 'chronolab.db')}"
    )


class ProductionConfig(Config):
    """Hardened production settings for cloud deployment (Render, Railway, AWS)."""
    DEBUG = False
    TESTING = False
    
    # Enforce secure cookies when HTTPS is active
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
    
    # Handle cloud PostgreSQL URLs (e.g., convert postgres:// to postgresql:// for SQLAlchemy)
    _db_url = os.environ.get("DATABASE_URL")
    if _db_url and _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = _db_url or f"sqlite:///{os.path.join(BASE_DIR, 'chronolab.db')}"


class TestingConfig(Config):
    """In-memory database for automated CI/CD unit and integration tests."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


# Configuration lookup map
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig
}
