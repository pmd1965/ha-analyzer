from __future__ import annotations

import os
from typing import ClassVar


class BaseConfig:
    SECRET_KEY: ClassVar[str] = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")
    SQLALCHEMY_DATABASE_URI: ClassVar[str] = os.environ.get(
        "DATABASE_URL", "sqlite:///ha_analyzer.sqlite"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS: ClassVar[dict] = {
        "connect_args": {"check_same_thread": False},
    }
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    INFLUXDB_URL: ClassVar[str] = os.environ.get("INFLUXDB_URL", "http://ha-influxdb:8086")
    INFLUXDB_TOKEN: ClassVar[str] = os.environ.get("INFLUXDB_TOKEN", "")
    INFLUXDB_ORG: ClassVar[str] = os.environ.get("INFLUXDB_ORG", "homelab")
    INFLUXDB_BUCKET: ClassVar[str] = os.environ.get("INFLUXDB_BUCKET", "homeassistant")

    OLLAMA_URL: ClassVar[str] = os.environ.get("OLLAMA_URL", "http://192.168.0.106:11434")
    OLLAMA_MODEL: ClassVar[str] = os.environ.get("OLLAMA_MODEL", "gemma4:31b")
    OLLAMA_TIMEOUT: ClassVar[int] = int(os.environ.get("OLLAMA_TIMEOUT", "180"))

    TELEGRAM_BOT_TOKEN: ClassVar[str] = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: ClassVar[str] = os.environ.get("TELEGRAM_CHAT_ID", "")

    MAIL_SMTP_HOST: ClassVar[str] = os.environ.get("MAIL_SMTP_HOST", "mail.hover.com")
    MAIL_SMTP_PORT: ClassVar[int] = int(os.environ.get("MAIL_SMTP_PORT", "587"))
    MAIL_USERNAME: ClassVar[str] = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD: ClassVar[str] = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM: ClassVar[str] = os.environ.get("MAIL_FROM", "philip@davidson.net")
    MAIL_TO: ClassVar[str] = os.environ.get("MAIL_TO", "philip@davidson.net")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI: ClassVar[str] = os.environ.get(
        "DATABASE_URL", "sqlite:///ha_analyzer_dev.sqlite"
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SQLALCHEMY_ENGINE_OPTIONS: ClassVar[dict] = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
        "pool_pre_ping": True,
    }


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    from sqlalchemy.pool import StaticPool

    SQLALCHEMY_ENGINE_OPTIONS: ClassVar[dict] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
