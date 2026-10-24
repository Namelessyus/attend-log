"""Server-side account authorization. Browser cookies never contain roles or passwords."""
from datetime import datetime, timedelta, timezone
from functools import wraps
from hashlib import sha256
from secrets import token_urlsafe

import click
from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from attendlog.db import LoginSession, LoginThrottle, SecurityEvent, TeacherInvitation, User
from attendlog.mail import send_invitation

bp = Blueprint("auth", __name__)
COOKIE = "attendlog_auth"
DUMMY_HASH = generate_password_hash("not-an-account-password")


def now():
    return datetime.now(timezone.utc)


def digest(value):
    return sha256(value.encode()).hexdigest()


def email_address(value):
    return validate_email(value.strip(), check_deliverability=False).normalized.lower()


def password_error(password, confirmation):
    if len(password) < 12 or len(password) > 128:
        return "Use a password between 12 and 128 characters."
    if password != confirmation:
        return "The passwords do not match."
    return None


def require_role(*roles):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("auth.login", next=request.path))
            if roles and g.user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorate


def safe_next(value):
    # A small explicit destination set avoids redirects to external or future endpoints.
    return value if value in {"/dashboard", "/admin/accounts", "/account"} else url_for("auth.dashboard")


def audit(action, target_id):
    g.db.add(SecurityEvent(action=action, actor_id=g.user.id if g.user else None, target_id=target_id))


def revoke_sessions(user_id):
    g.db.execute(update(LoginSession).where(LoginSession.user_id == user_id, LoginSession.revoked_at.is_(None)).values(revoked_at=now()))


def issue_session(user):
    old = request.cookies.get(COOKIE)
    if old:
        g.db.execute(update(LoginSession).where(LoginSession.token_digest == digest(old)).values(revoked_at=now()))
    token = token_urlsafe(32)
    g.db.add(LoginSession(token_digest=digest(token), user_id=user.id, expires_at=now() + timedelta(days=10)))
    session.clear()  # Rotate the anonymous CSRF session at authentication boundaries.
    return token


def attach_cookie(response, token):
    g.clear_auth_cookie = False
    response.set_cookie(COOKIE, token, max_age=10 * 24 * 60 * 60, httponly=True,
                        secure=current_app.config["SESSION_COOKIE_SECURE"], samesite="Lax", path="/")
    return response


def throttle_keys(email):
    return [(digest("email:" + email), 5), (digest("ip:" + (request.remote_addr or "unknown")), 30)]


def blocked(keys):
    cutoff = now() - timedelta(minutes=15)
    return any((row := g.db.get(LoginThrottle, key)) is not None and row.window_started_at > cutoff and row.failures >= limit
               for key, limit in keys)


def failed_attempt(keys):
    moment = now()
    cutoff = moment - timedelta(minutes=15)
    for key, _ in keys:
        statement = insert(LoginThrottle).values(key=key, failures=1, window_started_at=moment)
        g.db.execute(statement.on_conflict_do_update(index_elements=[LoginThrottle.key], set_={
            "failures": case((LoginThrottle.window_started_at <= cutoff, 1), else_=LoginThrottle.failures + 1),
            "window_started_at": case((LoginThrottle.window_started_at <= cutoff, moment), else_=LoginThrottle.window_started_at),
        }))
    g.db.commit()


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("auth.dashboard"))
    if g.db is None:
        abort(503)
    error = None
    destination = safe_next(request.values.get("next"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()[:254]
        password = request.form.get("password", "")
        keys = throttle_keys(email)
        if blocked(keys):
            return render_template("auth/login.html", error="Too many sign-in attempts. Try again in 15 minutes.", destination=destination), 429
        user = g.db.scalar(select(User).where(func.lower(User.email) == email))
        valid = check_password_hash(user.password_hash if user and user.password_hash else DUMMY_HASH, password[:129])
        if not valid or len(password) > 128 or not user or user.deleted_at or not user.email_verified_at:
            failed_attempt(keys)
            error = "The email or password is incorrect, or the account is not available."
        else:
            token = issue_session(user)
            g.db.execute(update(LoginThrottle).where(LoginThrottle.key == keys[0][0]).values(failures=0))
            g.db.commit()
            return attach_cookie(redirect(destination), token)
    return render_template("auth/login.html", error=error, destination=destination), 401 if error else 200


@bp.post("/logout")
@require_role()
def logout():
    g.login_session.revoked_at = now()
    g.db.commit()
    session.clear()
    response = redirect(url_for("auth.login"))
    response.delete_cookie(COOKIE, path="/", secure=current_app.config["SESSION_COOKIE_SECURE"], httponly=True, samesite="Lax")
    return response


@bp.get("/dashboard")
@require_role()
def dashboard():
    return render_template("auth/dashboard.html")


@bp.route("/account", methods=["GET", "POST"])
@require_role()
def account():
    error = None
    if request.method == "POST":
        current = request.form.get("current_password", "")
        password = request.form.get("password", "")
        confirmation = request.form.get("confirmation", "")
        if len(current) > 128 or not check_password_hash(g.user.password_hash, current):
            error = "Your current password is incorrect."
        else:
            error = password_error(password, confirmation)
            if not error and check_password_hash(g.user.password_hash, password):
                error = "Choose a different password."
        if not error:
            # Lock the user row so concurrent password changes cannot preserve an old session.
            g.db.refresh(g.user, with_for_update=True)
            if not check_password_hash(g.user.password_hash, current):
                error = "Your password changed. Please sign in again."
            else:
                g.user.password_hash = generate_password_hash(password)
                revoke_sessions(g.user.id)
                audit("password_changed", g.user.id)
                token = issue_session(g.user)
                g.db.commit()
                flash("Password changed. Your other sessions have been signed out.")
                return attach_cookie(redirect(url_for("auth.account")), token)
    return render_template("auth/account.html", error=error), 400 if error else 200


def prepare_invitation(user):
    g.db.execute(update(TeacherInvitation).where(TeacherInvitation.user_id == user.id, TeacherInvitation.consumed_at.is_(None)).values(consumed_at=now()))
    token = token_urlsafe(32)
    g.db.add(TeacherInvitation(token_digest=digest(token), user_id=user.id, expires_at=now() + timedelta(hours=48)))
    link = current_app.config["PUBLIC_URL"].rstrip("/") + url_for("auth.activate", token=token)
    send_invitation(user.email, link)


@bp.route("/admin/accounts", methods=["GET", "POST"])
@require_role("admin")
def accounts():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        try:
            email = email_address(request.form.get("email", ""))
            if not name or len(name) > 120:
                raise ValueError("Enter a name of up to 120 characters.")
            user = User(display_name=name, email=email, role="teacher")
            g.db.add(user)
            g.db.flush()
            prepare_invitation(user)
            audit("teacher_invited", user.id)
            g.db.commit()
            flash("Teacher invited." if current_app.config["MAIL_BACKEND"] == "smtp" else "Teacher invitation saved to the local outbox. Email delivery is not enabled.")
            return redirect(url_for("auth.accounts"))
        except (EmailNotValidError, ValueError) as exc:
            g.db.rollback()
            error = str(exc)
        except IntegrityError:
            g.db.rollback()
            error = "An account already uses this email. Use its existing account entry."
        except (OSError, RuntimeError) as exc:
            g.db.rollback()
            current_app.logger.warning("Invitation delivery failed (%s)", type(exc).__name__)
            error = "The invitation could not be delivered. No new account was saved."
    page = max(1, request.args.get("page", 1, type=int))
    users = g.db.scalars(select(User).order_by(User.created_at, User.id).offset((page - 1) * 20).limit(21)).all()
    return render_template("auth/accounts.html", users=users[:20], more=len(users) > 20, page=page, error=error), 400 if error else 200


@bp.post("/admin/accounts/<uuid:user_id>/<action>")
@require_role("admin")
def manage_account(user_id, action):
    user = g.db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not user:
        abort(404)
    if user.role == "admin" or user.id == g.user.id:
        abort(403)
    if action == "deactivate" and not user.deleted_at:
        user.deleted_at = now()
        revoke_sessions(user.id)
        g.db.execute(update(TeacherInvitation).where(TeacherInvitation.user_id == user.id).values(consumed_at=now()))
    elif action == "restore" and user.role == "teacher" and user.deleted_at:
        user.deleted_at = None
        # Class membership restoration is deliberately not performed here.
    elif action == "resend" and user.role == "teacher" and not user.deleted_at and not user.password_hash:
        try:
            prepare_invitation(user)
        except (OSError, RuntimeError):
            g.db.rollback()
            flash("Invitation delivery failed. Please try again.")
            return redirect(url_for("auth.accounts"))
    else:
        abort(400)
    audit("account_" + action, user.id)
    g.db.commit()
    flash("Account updated." if action != "resend" else "A new invitation has been prepared. The previous link is no longer valid.")
    return redirect(url_for("auth.accounts"))


@bp.route("/activate", methods=["GET", "POST"])
def activate():
    if g.db is None:
        abort(503)
    token = request.values.get("token", "")
    invitation = g.db.get(TeacherInvitation, digest(token[:200]))
    user = g.db.get(User, invitation.user_id) if invitation else None
    if request.method == "POST" and user and invitation:
        # Consistent lock order with account management: user, then invitation.
        g.db.refresh(user, with_for_update=True)
        g.db.refresh(invitation, with_for_update=True)
    if len(token) > 200 or not invitation or invitation.consumed_at or invitation.expires_at <= now() or not user or user.deleted_at or user.password_hash or user.role != "teacher":
        return render_template("auth/activate.html", invalid=True), 410
    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        error = password_error(password, request.form.get("confirmation", ""))
        if not error:
            if user.deleted_at or user.password_hash:
                abort(410)
            user.password_hash = generate_password_hash(password)
            user.email_verified_at = now()
            invitation.consumed_at = now()
            audit("teacher_activated", user.id)
            g.db.commit()
            flash("Your account is ready. Sign in with your email and password.")
            return redirect(url_for("auth.login"))
    return render_template("auth/activate.html", invalid=False, invited_user=user, token=token, error=error), 400 if error else 200


def init_app(app):
    @app.before_request
    def load_identity():
        g.user = g.login_session = None
        engine = app.extensions.get("database")
        g.db = Session(engine) if engine else None
        raw = request.cookies.get(COOKIE)
        if raw and g.db is not None and request.endpoint not in {"static", "live", "ready"}:
            record = g.db.get(LoginSession, digest(raw[:200])) if len(raw) <= 200 else None
            user = g.db.get(User, record.user_id) if record else None
            if record and not record.revoked_at and record.expires_at > now() and user and not user.deleted_at and user.password_hash and user.email_verified_at:
                g.user, g.login_session = user, record
            else:
                g.clear_auth_cookie = True

    @app.teardown_request
    def close_database(error):
        database = getattr(g, "db", None)
        if database is not None:
            database.close()

    @app.after_request
    def private_headers(response):
        if request.blueprint == "auth":
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
        if getattr(g, "clear_auth_cookie", False):
            response.delete_cookie(COOKIE, path="/")
        return response

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt=True)
    @click.password_option(confirmation_prompt=True)
    def create_admin(email, name, password):
        """Create an initial administrator locally; passwords are entered invisibly."""
        if not app.extensions.get("database"):
            raise click.ClickException("Configure DATABASE_URL first.")
        try:
            email = email_address(email)
        except EmailNotValidError as exc:
            raise click.ClickException(str(exc)) from exc
        error = password_error(password, password)
        if error or not name.strip() or len(name.strip()) > 120:
            raise click.ClickException(error or "Enter a name of up to 120 characters.")
        with Session(app.extensions["database"]) as db:
            if db.scalar(select(User).where(User.role == "admin", User.deleted_at.is_(None))):
                raise click.ClickException("An administrator already exists. Bootstrap is closed.")
            user = User(display_name=name.strip(), email=email, role="admin", password_hash=generate_password_hash(password), email_verified_at=now())
            db.add(user)
            try:
                db.commit()
            except IntegrityError as exc:
                raise click.ClickException("This email already belongs to an account.") from exc
        click.echo("Administrator created. Sign in through /login.")

    app.register_blueprint(bp)
