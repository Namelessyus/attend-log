# Phase-two validation — 24 October 2026

## Scope

Local email/password sign-in; database-backed roles; administrator bootstrap; teacher invitation and one-time activation; administrator account directory; teacher/student deactivation; teacher restoration; password changes; logout; revocable ten-day sessions. Work stays on local `codex/development`, with no push before its scheduled release.

Student self-registration, OTP verification, forgotten-password recovery, classes, and attendance remain later increments. The account workspace shows an honest empty class state; it does not invent classes or attendance statistics.

## Incremental checks

1. Added migration 0002 for hashed sessions, hashed invitations, persistent login throttles, and account security events. Foundation checks passed before adding account templates.
2. Added server-side authorization, CSRF protection, password hashing, activation, and account management. Initial tests exposed reserved-domain test fixtures; those were corrected to valid synthetic addresses without weakening the email validator.
3. Review found that an expired auth cookie could clear a newly issued login cookie. Fixed it and added a regression test. Activation uses consistent user/invitation row-lock order and is tested against simultaneous redemption.
4. Added screens that reuse the exact supplied palette and existing fonts/buttons/borders. The original landing-page CSS remains an unchanged prefix; all account rules are appended. Login/dashboard links now connect to their implemented routes.
5. Browser checks exposed native autofill's default blue background. Added a scoped autofill rule using Black Raspberry and Dove; no new palette colors were introduced.

## Automated result

**26 tests passed, with real PostgreSQL integration enabled and no skips.**

Command:

```sh
TEST_DATABASE_URL='postgresql+psycopg://anishdangol@/attendlog_phase1?host=/private/tmp/attendlog-phase1-pg&port=55439' .venv/bin/python -m pytest -q
```

The suite covers:

- Liveness/readiness, configuration failure for a missing private secret, safe activation origin configuration, and asset resolution.
- Migration upgrade/check/downgrade/re-upgrade, model/schema agreement, and preservation of existing user records and password hashes across 0001 ↔ 0002.
- Case-insensitive email uniqueness, invalid roles/empty class names, and soft-deletion history.
- All three roles can sign in; teachers and students cannot view or POST to the administrator directory. Submitted role fields cannot elevate invitations beyond teacher.
- HttpOnly/SameSite cookies, Secure cookies when configured for HTTPS, opaque hashed session records, ten-day server expiry, CSRF rotation on login, and safe redirect destinations.
- CSRF is required for POSTs; GET logout is rejected. Logout and password changes revoke replayed/other-session cookies. Login with an expired cookie successfully renews the session.
- Invalid login responses are generic; email throttles persist across clients and expire after the configured window. Disabled and unverified accounts cannot authenticate.
- Teacher tokens are hashed, one-time, time-limited, invalidated on resend, and cannot be redeemed simultaneously twice.
- Teacher activation enforces password length/confirmation and stores a scrypt hash. Administrators cannot see passwords.
- Deactivation revokes access immediately. Teacher restoration does not restore old sessions. Administrator deactivation and student restoration through the admin route are blocked.
- Invalid/duplicate teacher details are rejected. Delivery failure rolls back both account and invitation creation.
- Administrator bootstrap uses hidden password prompts and closes after an active administrator exists.

Additional checks: JavaScript syntax and Python compilation passed. `alembic check` on the live preview database reported “No new upgrade operations detected.” Updated Compose YAML passed the official Compose JSON schema.

## Browser result

Used only synthetic accounts in the isolated local preview database. No real emails were sent.

- Administrator login opens the administrator workspace and account directory; sign-out returns to login.
- Teacher login opens the teacher workspace, omits the administrator navigation, and direct navigation to `/admin/accounts` shows the themed access-restricted page.
- The password settings screen identifies only the current user.
- Login and account directory have no horizontal overflow at 320, 390, 768, 1024, and 1440 pixels; account-panel/input bounds remain inside the viewport for the tested account-directory widths.
- Computed palette values remain Dove #C0BAB3, Chocolate #52423D, Rock #887D77, Sienna #391214, and Black Raspberry #160F0C. Original fonts load locally.
- No unexpected browser warnings/errors were reported during the checks.

Evidence: [desktop sign-in](validation/phase2-login-desktop.jpg), [mobile sign-in](validation/phase2-login-mobile.jpg), [desktop accounts](validation/phase2-accounts-desktop.jpg), [mobile accounts](validation/phase2-accounts-mobile.jpg).

## Delivery and deployment limits

Local file-outbox invitation delivery and delivery-failure rollback are tested. SMTP configuration is implemented using STARTTLS, but real SMTP delivery is untested and was not exercised against an external mailbox.

Docker is still not installed on this laptop. Compose schema validation passed, but image build, migration-container execution, and container runtime behavior remain unverified. Local Gunicorn plus PostgreSQL execution passed.

New account-screen layouts extend the supplied visual system; they are not new user-approved immutable references. Continue preserving the original landing-page assets and palette when reviewing these screens.
