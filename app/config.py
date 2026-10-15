"""Application configuration loaded from environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _engine_options() -> dict:
    # pool_pre_ping discards dead connections; pool_recycle stays below the
    # idle timeout of shared MySQL hosts (PythonAnywhere closes them at 300 s).
    options = {"pool_pre_ping": True, "pool_recycle": 280}
    # Managed MySQL services (e.g. Aiven) require TLS: point this to their CA certificate.
    ssl_ca = os.environ.get("DATABASE_SSL_CA")
    if ssl_ca:
        options["connect_args"] = {"ssl": {"ca": ssl_ca}}
    return options


class Config:
    """Settings shared by every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options()

    ITEMS_PER_PAGE = int(os.environ.get("ITEMS_PER_PAGE", 15))
    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "America/Lima")
    CURRENCY_SYMBOL = "S/"
    BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "Mi Negocio")  # shown on reports
    # Public demo: shows the demo credentials on the login page and protects those accounts.
    DEMO_MODE = _flag("DEMO_MODE")

    # Built-in Spanish messages for WTForms validators (see app/forms/base.py).
    WTF_I18N_ENABLED = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    # Fast in-memory SQLite by default. Set TEST_DATABASE_URL to a dedicated MySQL test database
    # to also run the concurrency test (SQLite ignores SELECT ... FOR UPDATE).
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False  # forms are posted directly by the test client
    DEMO_MODE = False  # tests decide explicitly, a local .env must not change them


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    # Render and PythonAnywhere put a proxy in front of the app: trust its X-Forwarded-* headers
    # so Flask knows the real scheme (https) and client IP.
    BEHIND_PROXY = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
