# AttendLog build and weekly work plan

Prepared 24 October 2026. Status: phase-one foundation and landing-page baseline implemented and locally validated on 24 October 2026. Docker execution is pending because Docker is not installed; see PHASE_1_VALIDATION.md. The user approved genuine weekly work on eight Fridays at 17:00 Asia/Kathmandu.

## Source material and strict visual contract

- Original archive: `assets/source/attend-log.zip` (retained unchanged).
- Functional specification: `assets/instructions.txt` (retained unchanged).
- Primary landing-page reference: `assets/ui/landing pg ui.png`.
- Supporting references: Ledger, Scanner, and Bento HTML files under `assets/ui/`.
- Extract only assets; the archive also contains an unrelated embedded Git directory and sample hooks. Those were not installed into this checkout.
- The PNG is the working visual authority because it combines the Scanner hero, pipeline cards, Bento cards, and Ledger register. The user explicitly confirmed the landing-page image as the main reference on 24 October 2026.
- Preserve the screenshot's desktop composition: navigation, split hero and scanner, four pipeline cards, feature cards next to the register, final call to action, and footer. Match its spacing, typography, corners, borders, gradients, and proportions. Do not replace it with one of the three alternate HTML layouts.
- Lock the original shared tokens: Dove `#C0BAB3`, Chocolate `#52423D`, Rock `#887D77`, Sienna `#391214`, and dark background `#160F0C`. Ledger also defines Paper `#D6D1CB`. Preserve component-specific gradients, alpha values, and additional reference colors rather than approximating them with a new palette.
- Original typefaces: Scanner uses Space Grotesk; Ledger uses Newsreader and Instrument Sans; Bento uses DM Serif Display and DM Sans. Reuse the appropriate original styles for corresponding screenshot components. Resolve any uncertain screenshot/font mapping by comparison, not by choosing a new typeface.
- New admin, teacher, and student screens have no supplied full mockups. Extend the same tokens and component language; do not claim that their layouts were specified by the references. Confirm those new layouts before treating them as frozen references.
- Keep the original files immutable. Screenshots at a reference-sized desktop viewport and mobile widths will be used to compare the implementation visually. Correct visual deviations without redesigning.

## Intended first release

College attendance first, with a data model that can later accommodate offices and gyms. Incremental delivery, responsive web UI, and Docker-based local deployment.

### Roles and account lifecycle

- Admin/department management creates, edits, soft-deletes, and restores classes; registers teachers; and assigns, replaces, or removes teachers from classes.
- Teacher sees assigned classes, manages enrollment requests and class members, opens attendance windows, corrects records, and views reports for assigned classes.
- Student registers personal information and face data with consent, verifies email with an OTP, then joins classes through a code subject to teacher approval. Students see only their own records and graphs.
- OTP validity is 30 minutes, with expiry, resend throttling, attempt limits, and one-time consumption.
- Passwords are hashed; teachers never see student passwords. Teachers and students have password change and recovery flows.
- Sessions last approximately ten days. Logout revokes the current session; password changes and account deactivation revoke relevant outstanding sessions.
- Soft-deleted accounts can be recovered. Admins recover teacher accounts; student recovery requires the specified teacher verification. Account recovery does not automatically restore class memberships.
- Class codes can rotate. Repeated requests are idempotent; a removed student must request approval again.
- Class cards can be reordered by dragging, with order saved per user; provide an equivalent keyboard control without altering visual styling.

### Attendance and reporting

- Each class has explicitly scheduled class sessions/dates. No scheduled session means no absence.
- Attendance is separate for each class session, even for students enrolled in multiple classes.
- Track the roster eligible for each session, including enrollment validity dates, so later joins/removals do not rewrite historical absence totals.
- Present: accepted check-in during the on-time portion of an open session.
- Late: accepted check-in after the on-time deadline and before check-in closes.
- After check-in closes: an unmarked student receives “Timed out”.
- Save attendance records for successful check-ins. Do not insert absent rows. After closure, absence is derived from eligible approved students without an effective check-in.
- Duplicate check-ins return “Already marked”. Enforce uniqueness in PostgreSQL as well as in application logic.
- Check-out is disabled by default. When enabled, it has a separate teacher-controlled window. Repeated scans outside that window must not become check-outs.
- Check-out produces an estimated duration, not proof of continuous presence. Missing check-out leaves duration incomplete; never award full credit hours automatically.
- Teachers can reopen, extend, manually mark, and correct attendance for assigned classes. Record actor, timestamp, reason, and before/after values. Reports use the effective corrected result.
- Soft-deletion preserves historical reports. Recovered classes and accounts must not silently recreate expired/revoked access.
- Admin reports cover authorized classes, teachers see assigned classes, students see only themselves. Include present/late/derived-absent totals and graphs, with denominators based on scheduled eligible sessions.

## Process conflicts and proposed resolutions

These proposals preserve the requested UI. Resolve them before implementing the affected behavior.

1. **Names/emails are identification, not sufficient login credentials.** Admin-created teachers should receive a one-time activation link to set a password. Name remains display data; email plus password is used for login. Bootstrap the first administrator through a local management command, not public registration.
2. **The time example closes attendance at 09:10 but also allows late scans after 09:10.** Use three explicit values: opens_at, on_time_until, closes_at. Example for a 09:00–10:00 class: opens 09:00, on-time deadline 09:10, check-in closes at a later teacher-selected time. Exact boundary convention proposed: opens_at <= t <= on_time_until is present; on_time_until < t < closes_at is late; t >= closes_at is timed out. Validate the ordering on the server.
3. **The HTML says one row per person per day, while the requirements allow multiple classes.** Use a unique (student_id, class_session_id) check-in record. A scheduled session entity is required in the basic release; only more elaborate subject/timetable management is deferred.
4. **The HTML implies the next scan always checks out.** The written specification takes priority: check-out is optional, requires its own window, and otherwise repeated scans are duplicates. Preserve reference appearance while proposing truthful copy changes for approval.
5. **Local hosting alone does not prove presence.** Proposed first-release attendance capture: a teacher-controlled classroom webcam/kiosk. Student browsers handle registration, join requests, and personal reports; the teacher authorizes the attendance scanner. If individual student-phone attendance is required, first agree on a stronger proximity/anti-replay flow; do not claim LAN membership is proof of location.
6. **Email verification needs delivery; face matching may run locally.** Separate the claim “local face processing” from “fully offline application”. Use a development mail inbox for local testing and an actual SMTP service for real verification. Do not silently treat email OTP as offline.
7. **Registration approval needs face review, but HTML says no photo gallery is stored.** Decide whether teachers review a limited retained profile/enrollment photo or only metadata and registration status. Do not quietly retain all captured frames; define consent, retention, and deletion for any retained image. Keep real images and embeddings outside Git.
8. **Camera access on student phones is a deployment concern.** Browser camera capture requires a secure context; localhost works on the laptop, while LAN phone access needs trusted HTTPS. Include the phone camera path in deployment testing if phone registration is required.
9. **Recognition is fallible.** Start with the reference HOG/128-value embedding approach and 0.6 threshold as a baseline, then evaluate false matches and unknown faces using consenting demo participants. Do not mark unknown, ambiguous, or multiple-face captures automatically. Blink/liveness improvements remain a later phase, and the MVP must not claim photo-spoof resistance.
10. **Restore semantics and role reassignment need explicit rules.** Preserve membership history and authorization dates; restored students request approval again. Proposed teacher replacement removes future access for the replaced teacher while preserving historical authorship and correction logs.

Technical sources: [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia) and [face_recognition API](https://face-recognition.readthedocs.io/en/latest/face_recognition.html). These inform deployment and recognition evaluation; they do not override the user's design.

## Proposed implementation architecture

- Flask application with server-rendered templates, reference-derived CSS, and small JavaScript modules for the scanner, saved card order, and reports. This follows the supplied Flask reference and avoids a new UI framework changing the appearance.
- PostgreSQL with migrations, foreign keys, transactional uniqueness constraints, and soft-deletion timestamps.
- SQLAlchemy/Alembic proposed for data access and migrations; select compatible pinned versions during implementation.
- Main entities: User, server-side Session, EmailVerification/PasswordReset, Class, TeacherAssignment, ClassMembership with approval/history, ClassJoinCode, ClassSession, Attendance, FaceEnrollment, AuditEvent, UserClassOrder.
- Recognition runs locally on the server using frames captured in the browser; no external face-recognition API. Protect scanner endpoints by teacher/session authorization and validate captures server-side.
- Docker Compose web + database as the core deployment. Development SMTP testing can use an optional mail-service profile. Verify recognition native dependencies on this laptop early.
- Use UTC instants internally and an explicit institution timezone for scheduling and reports. Initial timezone: Asia/Kathmandu.
- Bundle permitted font/model assets for local operation rather than depending on runtime Google Fonts/model downloads. Store secrets in environment configuration and exclude runtime/uploads/database volumes from Git.
- The attendance service may be part of the same web deployment initially; split it only if demonstrated load requires it.

## Incremental delivery sequence

| Increment | Working outcome | Acceptance gate |
| --- | --- | --- |
| 1: Foundation and visual baseline | Docker project, schema/migrations, reference landing page, locked design tokens | App boots; migrations run; desktop/mobile reference comparison; no visual redesign |
| 2: Identity and roles | Admin bootstrap, teacher activation, student signup, OTP, login, recovery, revocable sessions | OTP expiry/attempt limits; hashed passwords; server-side role/ownership restrictions |
| 3: Class lifecycle and enrollment | Class CRUD and restore, teacher assignment, rotating class codes, approval queue, student removal/rejoin, saved card order | Cross-class isolation; duplicate join handling; restore does not restore membership |
| 4: Scheduled attendance | Scheduled session + eligible roster, independent deadlines, manual correction and audit log, derived absence | Deadline boundaries; unscheduled dates; same student in multiple classes; historical roster stability |
| 5: Face workflow | Consented registration, local encoding/matching, teacher-controlled scanner, unknown/duplicate outcomes | Capture quality; no match for unknowns; simultaneous scans produce one check-in; real camera test |
| 6: Optional check-out and graphs | Separate check-out window, incomplete duration state, role-filtered graphs and historical reports | Check-out off by default; repeated check-in is not check-out; corrected totals; history survives soft deletion |
| 7: Integration and demo | Responsive QA, database restore/recovery checks, test suite, demo guide | At least five student accounts in total, with one created live; separate teacher/student browser sessions |
| 8: Final review | Remaining bug fixes, reproducible setup, test evidence and handover | Fresh install and full demo pass; document remaining limitations honestly |

This is an order of work, not a requirement to delay completed changes until a later Friday. We can complete multiple increments today and commit them when actually done. Do not invent later work dates.

## Eight genuine Friday work sessions

Time: 17:00 Nepal time (Asia/Kathmandu). Each run uses the current implementation; if a planned increment is already finished, validate it and address actual defects rather than recreating it.

| Run | Friday | Focus |
| --- | --- | --- |
| 1 | 30 October 2026 | Fresh setup, design/reference fidelity, migrations and deployment |
| 2 | 6 November 2026 | Login, activation, OTP, session expiry/revocation, role isolation |
| 3 | 13 November 2026 | Classes, teacher assignments, enrollment requests, code rotation, restore |
| 4 | 20 November 2026 | Scheduled sessions, deadline boundaries, duplicates, absence computation |
| 5 | 27 November 2026 | Registration, camera/recognition accuracy, unknown and ambiguous faces |
| 6 | 4 December 2026 | Optional check-out, corrections, graphs and historical accuracy |
| 7 | 11 December 2026 | Full multi-role demo, responsive UI, recovery and reproducible setup |
| 8 | 18 December 2026 | Regression review, final fixes, handover and remaining limitations |

Each run should:

1. Confirm the canonical checkout, expected remote, Git identity, and a safe working-tree state. Read AGENTS.md, this plan, recent changes, and any updated user decisions.
2. Perform the week's real review/testing. If the relevant feature has not been implemented, document the actual blocker rather than inventing a pass or starting a large unapproved feature build.
3. Make focused fixes within the agreed requirements, preserving design/colors. Run meaningful targeted checks. Never alter the immutable references to make a comparison pass.
4. Record useful actual findings and exact commands/results in `docs/weekly/YYYY-MM-DD.md`. State unavailable tests or blocked dependencies accurately. Do not create repetitive filler solely to produce a commit.
5. Commit only the automation's reviewed changes with the real current timestamp, using the configured Anushma identity. Never include unrelated user changes, secrets, or face data. Push the resulting commit to the configured origin only when the branch/remote are verified and the push is a normal fast-forward.
6. If there are no meaningful changes, do not force a commit. If the tree is unsafe, a push fails, or permissions block access, preserve work and report the exact blocker; do not force-push, overwrite user work, or bypass approval.
7. Notify on completed work, useful findings, failure, or required user input. Stay quiet when nothing has changed and there is no action to take. Stop after the eighth run, 18 December 2026; do not continue the series beyond that date.

The user approved this truthful weekly-work scope on 24 October 2026. There is no guarantee of exactly eight commits: useful review/fix/documentation work determines whether a commit is warranted.

Local scheduled work requires this laptop to be on, the desktop app running, the checkout available, and required filesystem/network permissions. GitHub updates also need network access and the configured SSH key. If a run is missed, report the miss and use the actual timestamp for any later recovery run. Official setup guidance: https://learn.chatgpt.com/docs/automations.

## Open decisions before the affected implementation

- Confirm teacher-controlled kiosk capture versus attendance from each student's phone.
- Confirm the distinct on-time deadline and final check-in closing time.
- Confirm the teacher activation/password flow and which student information is mandatory.
- Confirm whether a limited review/profile photo is retained for enrollment approval.
- Choose email delivery for real OTP messages and whether phones need local HTTPS in the demo.
- Approve behavior-correct wording where the reference HTML's example copy conflicts with the specified system.
- Design the currently unspecified inner screens using the locked visual system before implementing their layouts.

The original planning step did not build the application. Phase one now implements the visual baseline, app factory, locked dependencies, database foundation/migration, and Docker configuration. Later features and unresolved process decisions remain outside this phase.
