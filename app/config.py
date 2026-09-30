"""Read environment at factory time, allowing isolated tests."""

import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes"}


def configuration():
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    production = os.getenv("APP_ENV", "development") == "production"
    return {
        "SECRET_KEY": os.getenv("SECRET_KEY"),
        "SQLALCHEMY_DATABASE_URI": os.getenv("DATABASE_URL", "sqlite:///ponto.db"),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True, "pool_recycle": 280},
        "APP_ENV": "production" if production else "development",
        "APP_TIMEZONE": "America/Sao_Paulo",
        "APPLICATION_ROOT": os.getenv("APPLICATION_ROOT", "/"),
        "SETUP_TOKEN": os.getenv("SETUP_TOKEN", ""),
        "SESSION_COOKIE_SECURE": env_bool("SESSION_COOKIE_SECURE", production),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=8),
        "MAX_CONTENT_LENGTH": 64 * 1024,
        "WTF_CSRF_TIME_LIMIT": 8 * 60 * 60,
        "PROXY_FOR_COUNT": int(os.getenv("PROXY_FOR_COUNT", "0")),
        "PROXY_PROTO_COUNT": int(os.getenv("PROXY_PROTO_COUNT", "0")),
        "PROXY_PREFIX_COUNT": int(os.getenv("PROXY_PREFIX_COUNT", "0")),
        "PREFERRED_URL_SCHEME": "https" if production else "http",
    }
