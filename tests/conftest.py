import os
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from attendlog.db import migration_config


@pytest.fixture(autouse=True)
def private_test_key(monkeypatch):
    monkeypatch.setenv("ATTENDLOG_SECRET_KEY", "test-only-key-not-for-deployment-" + uuid4().hex)


@pytest.fixture
def database(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database.")
    engine = create_engine(url)
    schema = "attendlog_test_" + uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    test_url = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", test_url)
    try:
        command.upgrade(migration_config(), "head")
        yield test_url
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
