import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from attendlog import create_app
from attendlog.db import Class, User, migration_config


def test_liveness_does_not_require_database():
    app = create_app({"TESTING": True, "DATABASE_URL": None})
    client = app.test_client()
    assert client.get("/health/live").json == {"status": "ok"}
    assert client.get("/health/ready").status_code == 503


def test_failed_readiness_does_not_leak_connection_details():
    app = create_app({"TESTING": True, "DATABASE_URL": "postgresql+psycopg://invalid:private@127.0.0.1:1/invalid"})
    response = app.test_client().get("/health/ready")
    assert response.status_code == 503
    assert response.json == {"status": "unavailable"}
    assert b"private" not in response.data


@pytest.fixture
def database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database.")
    engine = create_engine(url)
    # A unique schema keeps these migration tests away from existing application data.
    schema = "phase1_test_" + uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    from sqlalchemy.engine import make_url
    parsed = make_url(url)
    test_url = parsed.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url
    try:
        command.upgrade(migration_config(), "head")
        yield test_url
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_migration_roundtrip_and_schema_alignment(database):
    config = migration_config()
    command.downgrade(config, "base")
    app = create_app({"TESTING": True, "DATABASE_URL": database})
    assert app.test_client().get("/health/ready").status_code == 503
    command.upgrade(config, "head")
    command.check(config)
    assert app.test_client().get("/health/ready").status_code == 200
    command.downgrade(config, "base")
    engine = create_engine(database)
    assert "users" not in inspect(engine).get_table_names()
    assert app.test_client().get("/health/ready").status_code == 503
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
    app.extensions["database"].dispose()


def test_database_constraints_and_soft_deleted_history(database):
    engine = create_engine(database)
    with Session(engine) as session:
        user = User(display_name="Synthetic student", email="student@example.test", role="student")
        course = Class(name="English")
        session.add_all([user, course])
        session.commit()
        student_id, course_id = user.id, course.id
        for invalid in (
            User(display_name="Duplicate", email="STUDENT@example.test", role="student"),
            User(display_name="Invalid role", email="other@example.test", role="superadmin"),
            Class(name="  "),
        ):
            session.add(invalid)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
        user.deleted_at = datetime.now(timezone.utc)
        course.deleted_at = datetime.now(timezone.utc)
        session.commit()
        assert session.get(User, student_id).deleted_at is not None
        assert session.get(Class, course_id).deleted_at is not None
        assert session.scalar(select(User).where(User.id == student_id)) is not None
    engine.dispose()
