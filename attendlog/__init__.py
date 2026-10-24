"""Application factory. Importing this module never opens a database connection."""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from attendlog.db import migration_head


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        TEMPLATES_AUTO_RELOAD=False,
    )
    if test_config:
        app.config.update(test_config)

    database_url = app.config["DATABASE_URL"]
    if database_url:
        app.extensions["database"] = create_engine(
            database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3}
        )

    @app.get("/")
    def landing():
        # The illustration and register are the supplied sample content, not live data.
        notice = request.args.get("access")
        if notice not in {"login", "attendance", "dashboard"}:
            notice = None
        return render_template("landing.html", access_notice=notice)

    @app.get("/health/live")
    def live():
        return jsonify(status="ok")

    @app.get("/health/ready")
    def ready():
        engine = app.extensions.get("database")
        if engine is None:
            return jsonify(status="unavailable"), 503
        try:
            with engine.connect() as connection:
                if not inspect(connection).has_table("alembic_version"):
                    return jsonify(status="unavailable"), 503
                revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
                if revision != migration_head():
                    return jsonify(status="unavailable"), 503
        except SQLAlchemyError:
            app.logger.warning("Database readiness check failed")
            return jsonify(status="unavailable"), 503
        return jsonify(status="ok")

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", title="Page not found", message="This page could not be found."), 404

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    return app
