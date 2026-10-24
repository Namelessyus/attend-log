# AttendLog

Phase two: the reference landing page, local accounts, roles, and revocable sessions.
The original references live in `assets/`; the design contract is in `AGENTS.md`.
Read `docs/BUILD_PLAN.md` for the full incremental plan and open process decisions.

## What works now

- Responsive landing page based on `assets/ui/landing pg ui.png`, using the exact five-color palette and locally bundled original fonts.
- “How it works” section navigation, accessible dialogs, keyboard dismissal, and return focus.
- Email/password sign-in, role-specific workspaces, administrator account management, teacher invitations/activation, sign-out, and password changes. Attendance scanning is still unavailable; the landing scanner, chart, names, and register remain reference illustrations/sample data.
- Flask application factory, restricted static assets, liveness/readiness endpoints, locked dependencies, and a Gunicorn entry point.
- PostgreSQL schema and reversible Alembic migrations for users, classes, hashed server-side sessions, one-time teacher invitations, login throttling, and account audit events. No demo accounts or real personal/biometric records are seeded by application startup.

## Run locally (Python 3.12+)

Install [uv](https://docs.astral.sh/uv/) and use a dedicated PostgreSQL 15 database.

```sh
uv sync --frozen
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/attendlog'
export ATTENDLOG_SECRET_KEY="$(uv run python -c 'import secrets; print(secrets.token_hex(32))')"
uv run alembic upgrade head
uv run flask --app attendlog create-admin
uv run gunicorn --bind 127.0.0.1:8000 'attendlog:create_app()'
```

Open <http://127.0.0.1:8000>. Without `DATABASE_URL`, the landing page and `/health/live` still work, while `/health/ready` correctly returns 503. Do not point migrations or integration tests at an unrelated database. URL-encode special characters in connection credentials.

## Run with Docker

Docker Engine/Desktop and Compose v2 are required.

```sh
cp .env.example .env
# Edit .env: set a private database password and a random ATTENDLOG_SECRET_KEY.
# Generate a key with: uv run python -c "import secrets; print(secrets.token_hex(32))"
docker compose up --build -d
docker compose ps
docker compose exec web /opt/venv/bin/flask --app attendlog create-admin
```

Compose starts PostgreSQL, waits for it to become healthy, runs the migration service successfully, then starts the web service. The page is exposed only on `127.0.0.1:8000`. The database is not published to the host; its data lives in a named volume. Keep that volume when stopping the project.

```sh
docker compose down
```

Do not use `down --volumes` against a database whose contents you want to retain.
Docker execution has not yet been verified on the development laptop because Docker is not installed. See `docs/PHASE_1_VALIDATION.md` and `docs/PHASE_2_VALIDATION.md` for the checks actually performed.

## Validate

```sh
uv run pytest
# Integration checks use an isolated random schema in this disposable database.
TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/attendlog_test' uv run pytest
DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/attendlog' uv run alembic check
```

Without `TEST_DATABASE_URL`, database integration tests are explicitly skipped, not counted as passes. The integration tests create and drop only a random `phase1_test_...` schema, then run upgrade → check → downgrade → re-upgrade and database constraint checks.

Useful endpoints: `/health/live` checks the web process; `/health/ready` checks database connectivity and the current migration revision. Readiness failures return a generic response without database credentials.

## Design and scope

Core palette: Soft Dove `#C0BAB3`, Spiced Hot Chocolate `#52423D`, Moon Rock `#887D77`, Dark Sienna `#391214`, Black Raspberry `#160F0C`. The register's original Paper `#D6D1CB` and scanner illustration gradients remain from the supplied HTML. Fonts and their SIL Open Font Licenses are in `attendlog/static/fonts/`.

Do not redesign the landing page. Inner screens and the decisions recorded in the build plan belong to subsequent increments. Camera permissions are deliberately blocked on the phase-one page; future authorized scanner routes must receive an appropriately scoped policy.

## Accounts and roles

The initial administrator is created only through `create-admin`, which prompts invisibly for a password and closes bootstrap once an active administrator exists. There is no public administrator or teacher registration. Use `/login` with your email and password; the server reads your role from PostgreSQL rather than accepting a role from the browser.

Administrators use `/admin/accounts` to invite teachers, resend pending invitations, deactivate teacher/student accounts, and restore teacher accounts. Student restoration awaits teacher verification in a later increment. Administrators cannot deactivate administrator accounts through this interface. Deactivation revokes sessions and invitations. Restoration does not restore old sessions or class memberships.

Teacher invitation links expire after 48 hours and are usable once. Recipients set their own 12–128 character password. Passwords use Werkzeug scrypt hashes. Session and invitation secrets are stored only as SHA-256 digests in the database. Signed form cookies contain only CSRF/flash data; authenticated identity is held in a separate random HttpOnly cookie backed by a revocable database session. Sessions have an absolute ten-day lifetime. Logout revokes the current session; changing a password revokes every previous session and issues one new session for the current browser.

All POST forms use CSRF protection. Invalid login messages do not distinguish missing, disabled, unverified, or incorrect-password accounts. Failed logins are limited per normalized email (five) and peer IP (thirty) within a fifteen-minute window, stored in PostgreSQL so limits apply across workers. The application does not trust arbitrary forwarded-IP headers.

### Mail and deployment configuration

- `ATTENDLOG_SECRET_KEY`: required with DATABASE_URL; keep a private random value of at least 32 characters stable across workers/restarts. Never commit it.
- `ATTENDLOG_PUBLIC_URL`: canonical origin for activation links, default `http://127.0.0.1:8000`. HTTPS is required for non-loopback origins. Never derive invitation origins from an incoming Host header.
- `ATTENDLOG_COOKIE_SECURE=1`: use on HTTPS deployments. The local loopback-only HTTP configuration uses 0.
- `ATTENDLOG_MAIL_BACKEND=file`: default local development mode. Protected `.eml` messages are written to gitignored `runtime/mail`; they are not sent externally. In Docker, the outbox is stored in the `mail` named volume under `/app/runtime/mail`. To view filenames: `docker compose exec web ls /app/runtime/mail`. Do not share or commit invitation links.
- `ATTENDLOG_MAIL_BACKEND=smtp`: STARTTLS delivery using `ATTENDLOG_SMTP_HOST`, `ATTENDLOG_SMTP_PORT` (default 587), `ATTENDLOG_SMTP_USER`, `ATTENDLOG_SMTP_PASSWORD`, and `ATTENDLOG_MAIL_FROM`. Real SMTP delivery has not been tested; local outbox delivery and delivery-failure rollback have.

The provided Docker command deliberately excludes query strings and referrers from access logs so activation tokens are not logged. Use that same logging policy if adding your own server/proxy. Do not expose the local mail outbox, runtime directory, or private environment files through a web server.

Public student signup, student OTP verification, forgotten-password recovery, class membership, and attendance remain subsequent increments. Current account workspaces accurately show no classes until those features are implemented.

## Local development and scheduled publication

Keep work on local `codex/development`. Do not push it. `docs/RELEASE_PLAN.md` records the exact commit to publish on each Friday; the first account release is scheduled for 30 October 2026 at 17:00 Nepal time. Only the scheduled exact commit may be pushed by the automation.
