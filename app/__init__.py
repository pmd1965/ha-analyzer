from __future__ import annotations

import logging

import structlog
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import config_map

logger = structlog.get_logger(__name__)


def create_app(config_name: str = "production") -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_map[config_name])
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    _configure_logging(app)
    _init_extensions(app)
    _register_blueprints(app)
    _apply_security_headers(app)

    if not app.testing:
        _start_scheduler(app)

    logger.info("app_started", env=config_name)
    return app


def _configure_logging(app: Flask) -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG if app.debug else logging.INFO,
    )


def _init_extensions(app: Flask) -> None:
    import sqlite3

    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    from app.extensions import csrf, db, migrate

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    @event.listens_for(Engine, "connect")
    def _set_sqlite_wal(dbapi_conn: object, _record: object) -> None:
        if isinstance(dbapi_conn, sqlite3.Connection):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")


def _register_blueprints(app: Flask) -> None:
    from app.blueprints.analysis import bp as analysis_bp
    from app.blueprints.api import bp as api_bp
    from app.blueprints.main import bp as main_bp
    from app.blueprints.scenarios import bp as scenarios_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(scenarios_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(api_bp)


def _apply_security_headers(app: Flask) -> None:
    @app.after_request
    def _set_headers(response):  # type: ignore[no-untyped-def]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "same-origin"
        return response


def _start_scheduler(app: Flask) -> None:
    from app.services.scheduler import start_scheduler

    start_scheduler(app)
