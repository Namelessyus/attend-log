from datetime import timedelta

from sqlalchemy.orm import Session

from attendlog.auth import COOKIE, digest, now
from attendlog.db import LoginSession
from test_auth import app, csrf, invite, login, post, PASSWORD
from sqlalchemy import select
from attendlog.db import User, TeacherInvitation


def test_login_replaces_an_expired_cookie_without_deleting_the_new_cookie(app):
    client = app.test_client()
    login(client)
    token = client.get_cookie(COOKIE).value
    csrf_token = csrf(client,"/account")
    with Session(app.extensions["database"]) as db:
        db.get(LoginSession,digest(token)).expires_at = now()-timedelta(seconds=1)
        db.commit()
    response = client.post("/login",data={"csrf_token":csrf_token,"email":"admin@example.test","password":PASSWORD})
    assert response.status_code == 302
    assert client.get_cookie(COOKIE) is not None
    assert client.get_cookie(COOKIE).value != token
    assert client.get("/dashboard").status_code == 200


def test_only_one_concurrent_activation_consumes_invitation(app):
    from concurrent.futures import ThreadPoolExecutor
    admin = app.test_client()
    login(admin)
    token = invite(admin,app)
    clients = [app.test_client(),app.test_client()]
    tokens = [csrf(client,"/activate?token="+token) for client in clients]
    def activate(index):
        return clients[index].post("/activate",data={"csrf_token":tokens[index],"token":token,"password":PASSWORD,"confirmation":PASSWORD}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(activate,[0,1]))
    assert statuses == [302,410]


def test_delivery_failure_rolls_back_teacher_and_invitation(app,monkeypatch):
    def fail(*args):
        raise OSError("synthetic delivery failure")
    monkeypatch.setattr("attendlog.auth.send_invitation",fail)
    admin = app.test_client()
    login(admin)
    response = post(admin,"/admin/accounts",{"name":"Undelivered","email":"undelivered@example.com"},"/admin/accounts")
    assert response.status_code == 400
    with Session(app.extensions["database"]) as db:
        assert db.scalar(select(User).where(User.email=="undelivered@example.com")) is None
        assert db.scalar(select(TeacherInvitation)) is None


def test_expired_invitation_cannot_be_redeemed(app):
    admin = app.test_client()
    login(admin)
    token = invite(admin,app)
    recipient = app.test_client()
    csrf_token = csrf(recipient,"/activate?token="+token)
    with Session(app.extensions["database"]) as db:
        db.get(TeacherInvitation,digest(token)).expires_at = now()-timedelta(seconds=1)
        db.commit()
    assert recipient.post("/activate",data={"csrf_token":csrf_token,"token":token,"password":PASSWORD,"confirmation":PASSWORD}).status_code == 410


def test_invalid_teacher_details_and_duplicate_email_do_not_create_accounts(app):
    admin = app.test_client()
    login(admin)
    invite(admin,app)
    for fields in [{"name":"","email":"person@example.com"},{"name":"A","email":"invalid"},{"name":"A","email":"NEWTEACHER@EXAMPLE.COM"}]:
        assert post(admin,"/admin/accounts",fields,"/admin/accounts").status_code == 400
    with Session(app.extensions["database"]) as db:
        assert len(db.scalars(select(User)).all()) == 4


def test_https_configuration_sets_secure_cookies(app):
    app.config.update(SESSION_COOKIE_SECURE=True)
    response = login(app.test_client())
    assert any("attendlog_auth=" in value and "Secure" in value and "HttpOnly" in value and "SameSite=Lax" in value for value in response.headers.getlist("Set-Cookie"))


def test_account_migration_preserves_existing_users_on_upgrade_and_downgrade(database):
    from alembic import command
    from attendlog.db import migration_config
    from sqlalchemy import create_engine
    from werkzeug.security import generate_password_hash
    config = migration_config()
    command.downgrade(config,"0001_foundation")
    engine = create_engine(database)
    password_hash = generate_password_hash(PASSWORD)
    with Session(engine) as db:
        user = User(display_name="Existing account",email="existing@example.com",role="student",password_hash=password_hash,email_verified_at=now())
        db.add(user)
        db.commit()
        user_id = user.id
    command.upgrade(config,"head")
    with Session(engine) as db:
        assert db.get(User,user_id).password_hash == password_hash
    command.downgrade(config,"0001_foundation")
    with Session(engine) as db:
        assert db.get(User,user_id).email == "existing@example.com"
    command.upgrade(config,"head")
    command.check(config)
    engine.dispose()
