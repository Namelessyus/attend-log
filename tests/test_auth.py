from datetime import timedelta
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from attendlog import create_app
from attendlog.auth import COOKIE, digest, now
from attendlog.db import LoginSession, LoginThrottle, TeacherInvitation, User

PASSWORD = "Synthetic-only-passphrase-42"


@pytest.fixture
def app(database, tmp_path):
    app = create_app({"TESTING": True, "DATABASE_URL": database, "MAIL_OUTBOX": str(tmp_path / "mail")})
    with Session(app.extensions["database"]) as db:
        for role in ["admin", "teacher", "student"]:
            db.add(User(display_name="Synthetic " + role, email=role+"@example.test", role=role,
                        password_hash=generate_password_hash(PASSWORD), email_verified_at=now()))
        db.commit()
    yield app
    app.extensions["database"].dispose()


def csrf(client, path="/login"):
    response = client.get(path)
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.text)
    assert match, response.text
    return match[1]


def login(client, role="admin", password=PASSWORD, destination="/dashboard"):
    return client.post("/login", data={"csrf_token": csrf(client), "email": role+"@example.test", "password": password, "next": destination})


def post(client, path, fields=None, csrf_path="/account"):
    return client.post(path, data={"csrf_token": csrf(client, csrf_path), **(fields or {})})


def invite(client, app, email="newteacher@example.com", extra=None):
    response = post(client, "/admin/accounts", {"name":"New Teacher", "email":email, **(extra or {})}, "/admin/accounts")
    assert response.status_code == 302
    from pathlib import Path
    message = sorted(Path(app.config["MAIL_OUTBOX"]).glob("*.eml"), key=lambda p:p.stat().st_mtime)[-1].read_text()
    # The email library may quoted-printable encode long query strings.
    from email import message_from_string, policy
    body = message_from_string(message, policy=policy.default).get_content()
    link = re.search(r"http://[^\s]+", body)[0]
    return parse_qs(urlsplit(link).query)["token"][0]


def test_roles_cannot_escalate_or_read_account_directory(app):
    for role in ["teacher", "student"]:
        client = app.test_client()
        assert login(client, role).status_code == 302
        assert client.get("/dashboard").status_code == 200
        assert client.get("/admin/accounts").status_code == 403
        assert post(client, "/admin/accounts", {"name":"Attack", "email":"attack@example.test", "role":"admin"}).status_code == 403
    guest = app.test_client()
    assert guest.get("/admin/accounts").status_code == 302


def test_login_cookie_csrf_rotation_and_safe_redirect(app):
    client = app.test_client()
    before = csrf(client)
    response = client.post("/login", data={"csrf_token":before, "email":"ADMIN@EXAMPLE.TEST", "password":PASSWORD, "role":"superadmin", "next":"https://evil.example"})
    assert response.location == "/dashboard"
    cookie = client.get_cookie(COOKIE)
    assert cookie.http_only and cookie.same_site == "Lax"
    assert csrf(client, "/account") != before
    with Session(app.extensions["database"]) as db:
        record = db.get(LoginSession, digest(cookie.value))
        assert record is not None
        assert timedelta(days=9, hours=23) < record.expires_at-now() <= timedelta(days=10)
        assert record.token_digest != cookie.value
    assert client.get("/dashboard").headers["Cache-Control"] == "no-store"


def test_post_requires_csrf_and_logout_revokes_copied_cookie(app):
    client = app.test_client()
    assert client.post("/login", data={"email":"admin@example.test", "password":PASSWORD}).status_code == 400
    login(client)
    token = client.get_cookie(COOKIE).value
    assert client.post("/logout").status_code == 400
    assert client.get("/logout").status_code == 405
    assert post(client, "/logout").status_code == 302
    replay = app.test_client()
    replay.set_cookie(COOKIE, token)
    assert replay.get("/dashboard").status_code == 302


def test_expired_unverified_and_deleted_accounts_cannot_authenticate(app):
    client = app.test_client()
    login(client, "student")
    token = client.get_cookie(COOKIE).value
    with Session(app.extensions["database"]) as db:
        db.get(LoginSession, digest(token)).expires_at = now()-timedelta(seconds=1)
        db.commit()
    assert client.get("/dashboard").status_code == 302
    for field, value in [("email_verified_at",None),("deleted_at",now())]:
        with Session(app.extensions["database"]) as db:
            user = db.scalar(select(User).where(User.role=="teacher"))
            user.email_verified_at = now()
            user.deleted_at = None
            setattr(user,field,value)
            db.commit()
        assert login(app.test_client(), "teacher").status_code == 401


def test_invalid_login_is_generic_and_persistently_throttled(app):
    client = app.test_client()
    message = None
    for attempt in range(5):
        response = login(client, "student", "incorrect")
        assert response.status_code == 401
        message = response.text
    assert login(app.test_client(), "student").status_code == 429
    unknown = login(app.test_client(), "missing", "incorrect")
    assert unknown.status_code == 401
    assert "The email or password is incorrect, or the account is not available." in unknown.text
    with Session(app.extensions["database"]) as db:
        db.execute(update(LoginThrottle).values(window_started_at=now()-timedelta(minutes=16)))
        db.commit()
    assert login(app.test_client(), "student").status_code == 302


def test_password_change_requires_current_and_revokes_other_sessions(app):
    first, second = app.test_client(), app.test_client()
    login(first, "teacher")
    login(second, "teacher")
    old_cookie = first.get_cookie(COOKIE).value
    assert post(first, "/account", {"current_password":"wrong", "password":"new-password-1234", "confirmation":"new-password-1234"}).status_code == 400
    response = post(first, "/account", {"current_password":PASSWORD, "password":"new-password-1234", "confirmation":"new-password-1234"})
    assert response.status_code == 302
    assert first.get_cookie(COOKIE).value != old_cookie
    assert first.get("/dashboard").status_code == 200
    assert second.get("/dashboard").status_code == 302
    assert login(app.test_client(), "teacher", PASSWORD).status_code == 401
    assert login(app.test_client(), "teacher", "new-password-1234").status_code == 302


def test_invitation_role_is_fixed_hashed_single_use_and_activates(app):
    admin = app.test_client()
    login(admin)
    token = invite(admin, app, extra={"role":"admin"})
    with Session(app.extensions["database"]) as db:
        user = db.scalar(select(User).where(User.email=="newteacher@example.com"))
        assert user.role == "teacher" and user.password_hash is None
        assert db.get(TeacherInvitation, digest(token)) is not None
    teacher = app.test_client()
    path = "/activate?token="+token
    assert post(teacher, "/activate", {"token":token, "password":"short", "confirmation":"short"}, path).status_code == 400
    assert post(teacher, "/activate", {"token":token, "password":PASSWORD, "confirmation":PASSWORD}, path).status_code == 302
    assert teacher.get(path).status_code == 410
    with Session(app.extensions["database"]) as db:
        user = db.scalar(select(User).where(User.email=="newteacher@example.com"))
        assert user.password_hash != PASSWORD and check_password_hash(user.password_hash,PASSWORD)
        assert user.email_verified_at is not None
    assert teacher.post("/login", data={"csrf_token":csrf(teacher),"email":"newteacher@example.com","password":PASSWORD}).status_code == 302


def test_resend_invalidates_previous_invitation_and_expiry_is_enforced(app):
    admin = app.test_client()
    login(admin)
    token = invite(admin,app)
    with Session(app.extensions["database"]) as db:
        user = db.scalar(select(User).where(User.email=="newteacher@example.com"))
        user_id = user.id
    assert post(admin,f"/admin/accounts/{user_id}/resend",csrf_path="/admin/accounts").status_code == 302
    assert app.test_client().get("/activate?token="+token).status_code == 410
    with Session(app.extensions["database"]) as db:
        db.execute(update(TeacherInvitation).values(expires_at=now()-timedelta(seconds=1)))
        db.commit()
    assert app.test_client().get("/activate?token=invalid").status_code == 410


def test_deactivate_and_restore_teacher_do_not_restore_old_sessions(app):
    admin, teacher = app.test_client(), app.test_client()
    login(admin)
    login(teacher,"teacher")
    with Session(app.extensions["database"]) as db:
        users = {user.role:user.id for user in db.scalars(select(User))}
    assert post(admin,f"/admin/accounts/{users['admin']}/deactivate",csrf_path="/admin/accounts").status_code == 403
    assert post(admin,f"/admin/accounts/{users['teacher']}/deactivate",csrf_path="/admin/accounts").status_code == 302
    assert teacher.get("/dashboard").status_code == 302
    assert post(admin,f"/admin/accounts/{users['teacher']}/restore",csrf_path="/admin/accounts").status_code == 302
    assert teacher.get("/dashboard").status_code == 302
    assert login(teacher,"teacher").status_code == 302
    assert post(admin,f"/admin/accounts/{users['student']}/restore",csrf_path="/admin/accounts").status_code == 400


def test_bootstrap_creates_one_admin_with_hidden_password_input(database):
    app = create_app({"TESTING":True,"DATABASE_URL":database})
    runner = app.test_cli_runner()
    result = runner.invoke(args=["create-admin","--email","bootstrap@example.com","--name","Bootstrap"],input=PASSWORD+"\n"+PASSWORD+"\n")
    assert result.exit_code == 0, result.output
    assert PASSWORD not in result.output
    result = runner.invoke(args=["create-admin","--email","second@example.com","--name","Second"],input=PASSWORD+"\n"+PASSWORD+"\n")
    assert result.exit_code != 0
    app.extensions["database"].dispose()


def test_configuration_requires_private_key_and_safe_public_origin(monkeypatch):
    monkeypatch.delenv("ATTENDLOG_SECRET_KEY")
    with pytest.raises(RuntimeError,match="ATTENDLOG_SECRET_KEY"):
        create_app({"DATABASE_URL":"postgresql+psycopg://localhost/test"})
    with pytest.raises(RuntimeError,match="PUBLIC_URL"):
        create_app({"DATABASE_URL":None,"PUBLIC_URL":"http://external.example"})
