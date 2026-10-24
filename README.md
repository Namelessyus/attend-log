# AttendLog

Phase one: the reference landing page and a tested Flask/PostgreSQL foundation.
The original references live in `assets/`; the design contract is in `AGENTS.md`.
Read `docs/BUILD_PLAN.md` for the full incremental plan and open process decisions.

## What works now

- Responsive landing page based on `assets/ui/landing pg ui.png`, using the exact five-color palette and locally bundled original fonts.
- “How it works” section navigation, accessible dialogs, keyboard dismissal, and return focus.
- The login, attendance, and dashboard buttons explain that these features are not available yet. They do not log anyone in, access a camera, or save attendance. The scanner, chart, names, and register are reference illustrations/sample data.
- Flask application factory, restricted static assets, liveness/readiness endpoints, locked dependencies, and a Gunicorn entry point.
- PostgreSQL schema and reversible Alembic migration for soft-deletable users and classes. No demo accounts or real personal/biometric records are seeded.

## Run locally (Python 3.12+)

Install [uv](https://docs.astral.sh/uv/) and use a dedicated PostgreSQL 15 database.

```sh
uv sync --frozen
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/attendlog'
uv run alembic upgrade head
uv run gunicorn --bind 127.0.0.1:8000 'attendlog:create_app()'
```

Open <http://127.0.0.1:8000>. Without `DATABASE_URL`, the landing page and `/health/live` still work, while `/health/ready` correctly returns 503. Do not point migrations or integration tests at an unrelated database. URL-encode special characters in connection credentials.

## Run with Docker

Docker Engine/Desktop and Compose v2 are required.

```sh
cp .env.example .env
# Edit .env and replace the example database password before starting.
docker compose up --build -d
docker compose ps
```

Compose starts PostgreSQL, waits for it to become healthy, runs the migration service successfully, then starts the web service. The page is exposed only on `127.0.0.1:8000`. The database is not published to the host; its data lives in a named volume. Keep that volume when stopping the project.

```sh
docker compose down
```

Do not use `down --volumes` against a database whose contents you want to retain.
Docker execution has not yet been verified on the development laptop because Docker is not installed. See `docs/PHASE_1_VALIDATION.md` for the checks actually performed.

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
