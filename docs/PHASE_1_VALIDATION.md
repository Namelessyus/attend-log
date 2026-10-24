# Phase-one validation — 24 October 2026

## Scope completed

Reference landing page; responsive styles with the exact supplied color tokens; locally bundled original fonts and licenses; keyboard-accessible unavailable-feature notices; Flask app factory and Gunicorn entry point; PostgreSQL user/class foundation with soft-deletion timestamps; reversible migrations; locked dependencies; Dockerfile and Compose configuration.

No authentication, enrollment, camera recognition, attendance recording, or live dashboard has been implemented. The landing-page samples reproduce the supplied reference. Future-feature buttons clearly explain their unavailable status; they never open a camera or claim to authenticate.

## Step 1: foundation before UI

Python 3.12.15, PostgreSQL 15, uv 0.12.23. Dependencies resolved and frozen in uv.lock. An isolated temporary PostgreSQL instance used a private Unix socket and a dedicated attendlog_phase1 database; existing laptop databases were untouched.

Foundation suite: **4 passed** before adding the landing page. Verified:

- Liveness without a database and unavailable readiness without configuration.
- A database connection failure returns generic 503 without exposing credentials.
- Migration upgrade, Alembic model/schema check, downgrade, and re-upgrade.
- Case-insensitive email uniqueness, allowed roles, rejection of blank class names, and retention of soft-deleted rows.

Integration tests now create their own random schema and migrate it independently, so their result does not depend on test order. They drop only that schema afterward.

## Step 2: page and assets

Full suite: **8 passed**, including PostgreSQL checks (no integration-test skips).

```sh
TEST_DATABASE_URL='postgresql+psycopg://anishdangol@/attendlog_phase1?host=/private/tmp/attendlog-phase1-pg&port=55439' .venv/bin/python -m pytest -q
```

Additional checks:

- Every linked local asset and font resolves successfully; no external runtime asset dependency.
- Anchor targets exist, future-feature fallbacks render accurately, unknown access parameters are ignored, and missing pages offer a working return link.
- .env, .git/config, and the original ZIP are not exposed through Flask routes.
- CSP disallows remote/inline scripts and the landing-page permissions policy blocks camera/microphone access.
- `node --check attendlog/static/js/site.js` passed.
- Python compile check passed.
- `alembic check` on the actual preview database: “No new upgrade operations detected.”
- Gunicorn booted with two workers; live `/health/ready` returned HTTP 200 and `{"status":"ok"}`.

## Step 3: browser verification

Verified in the app's browser:

- No horizontal overflow or out-of-viewport component bounds at 320, 390, 768, 1024, 1440, and 1920 pixels.
- Pipeline uses one column on small phones, two on tablet, and four on desktop; the hero and feature sections stack appropriately.
- Admin login, live attendance, and dashboard each open the correct native modal notice.
- Escape dismisses the notice and restores focus to its triggering control; the return button closes it.
- “How it works” navigates to the process section.
- No console warnings or errors during these checks.
- Original fonts reported loaded. Computed background is RGB(22,15,12), heading text RGB(192,186,179), Sienna card RGB(57,18,20), Paper register RGB(214,209,203), and highlighted row RGB(192,186,179). All five original CSS hex tokens were checked directly.
- Desktop was compared against the 1920×2045 supplied PNG. Rendered page is 1920×2043. Section order, hero/scanner composition, pipeline, feature/register grid, and CTA were retained. Measurement-driven refinements corrected scanner face placement, register colors, and card spacing. This is visual comparison, not a claim of an automated pixel-perfect match.

Screenshots: [desktop](validation/desktop-final.jpg), [mobile](validation/mobile-final.jpg). The browser produces compressed captures; color values are verified against computed CSS rather than assuming equality of compressed screenshot pixels.

## Step 4: Docker configuration

Compose YAML parsed and passed the official Compose specification's JSON schema. The configuration waits for database health and successful migrations before launching web, publishes the web port on loopback only, leaves the database port unpublished, and persists PostgreSQL data in a named volume. The image runs as a non-root user and uses the frozen lockfile.

**Limit:** Docker Engine/Desktop and Compose are not installed on this laptop. Image build, container startup, and container health have not been executed or certified. Local Python/PostgreSQL execution passed; it does not substitute for a real Docker run. The Docker acceptance gate remains pending.

## Remaining scope

Next increment is accounts and roles. Keep it separate from the approved landing-page baseline, resolve the documented activation/enrollment decisions before implementing affected behavior, and continue running targeted tests after each increment. No claim of overall application completeness is made by these phase-one results.
