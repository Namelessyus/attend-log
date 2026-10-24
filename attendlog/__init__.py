"""Application factory. Importing this module never opens a database connection."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from flask_wtf.csrf import CSRFError, CSRFProtect

from attendlog.db import migration_head


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        TEMPLATES_AUTO_RELOAD=False,
        SECRET_KEY=os.environ.get("ATTENDLOG_SECRET_KEY"),
        SESSION_COOKIE_NAME="attendlog_form",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("ATTENDLOG_COOKIE_SECURE", "0") == "1",
        PUBLIC_URL=os.environ.get("ATTENDLOG_PUBLIC_URL", "http://127.0.0.1:8000"),
        MAIL_BACKEND=os.environ.get("ATTENDLOG_MAIL_BACKEND", "file"),
        MAIL_OUTBOX=os.environ.get("ATTENDLOG_MAIL_OUTBOX", str(Path(__file__).resolve().parent.parent / "runtime/mail")),
        MAIL_FROM=os.environ.get("ATTENDLOG_MAIL_FROM", "AttendLog <noreply@attendlog.local>"),
        SMTP_HOST=os.environ.get("ATTENDLOG_SMTP_HOST", ""),
        SMTP_PORT=int(os.environ.get("ATTENDLOG_SMTP_PORT", "587")),
        SMTP_USER=os.environ.get("ATTENDLOG_SMTP_USER", ""),
        SMTP_PASSWORD=os.environ.get("ATTENDLOG_SMTP_PASSWORD", ""),
    )
    if test_config:
        app.config.update(test_config)

    database_url = app.config["DATABASE_URL"]
    if database_url and (not app.config["SECRET_KEY"] or len(app.config["SECRET_KEY"]) < 32):
        raise RuntimeError("Set ATTENDLOG_SECRET_KEY to a private random value of at least 32 characters.")
    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = secrets.token_hex(32)
    public_url = urlsplit(app.config["PUBLIC_URL"])
    if public_url.username or public_url.password or public_url.query or public_url.fragment or public_url.path not in {"", "/"} or not public_url.hostname or (public_url.scheme != "https" and not (public_url.scheme == "http" and public_url.hostname in {"localhost", "127.0.0.1", "::1"})):
        raise RuntimeError("ATTENDLOG_PUBLIC_URL must be an HTTPS origin, or HTTP on localhost.")
    if database_url:
        app.extensions["database"] = create_engine(
            database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3}
        )

    from attendlog.auth import init_app
    init_app(app)
    CSRFProtect(app)

    @app.get("/")
    def landing():
        # The illustration and register are the supplied sample content, not live data.
        notice = request.args.get("access")
        if notice in {"login", "dashboard"}:
            from flask import redirect, url_for
            return redirect(url_for("auth.login" if notice == "login" else "auth.dashboard"))
        if notice != "attendance":
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

    @app.errorhandler(CSRFError)
    def invalid_form(error):
        return render_template("error.html", title="Please try again", message="This form expired or could not be verified. Reload the page and try again."), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", title="Access restricted", message="Your account does not have permission to open this page."), 403

    @app.errorhandler(503)
    @app.errorhandler(SQLAlchemyError)
    def unavailable(error):
        from flask import g
        if getattr(g, "db", None) is not None:
            g.db.rollback()
        app.logger.warning("Account service unavailable (%s)", type(error).__name__)
        return render_template("error.html", title="Temporarily unavailable", message="Account access is temporarily unavailable. Please try again shortly."), 503

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
