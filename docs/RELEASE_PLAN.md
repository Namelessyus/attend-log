# AttendLog scheduled releases

User clarification, 24 October 2026: complete development in advance and push eight prepared increments on Fridays. These are publication dates, not claims about when the code was written. All commits retain their actual author and committer dates.

Development branch: local `codex/development`. Published branch: `origin/main`.
Existing published baseline: `d10b0e9` (24 October 2026). Preserve it.

The scope below is a proposed breakdown of remaining work. Exact full commit IDs must be recorded after implementation and validation. Until then, each release is blocked; the automation must not guess a commit or push the latest development head.

| Friday, 17:00 Nepal time | Proposed increment | Verified full commit ID |
| --- | --- | --- |
| 30 October 2026 | Authentication, roles, teacher activation, sessions | Pending |
| 6 November 2026 | Student registration, email verification, password recovery | Pending |
| 13 November 2026 | Classes, teacher assignment, soft deletion and restoration | Pending |
| 20 November 2026 | Class codes, enrollment approvals, member management | Pending |
| 27 November 2026 | Scheduled attendance, timing, duplicate handling, corrections | Pending |
| 4 December 2026 | Face enrollment and classroom scanner integration | Pending |
| 11 December 2026 | Optional check-out, graphs, role-filtered historical reports | Pending |
| 18 December 2026 | Final regression fixes, full demo and handover | Pending |

Each assigned commit must descend from the previous release and contain only that increment and its prerequisites. Build and test each release state, including migrations, before assigning its commit ID. Preserve a complete working final version locally on the development branch.

On each scheduled date, verify the expected remote and preceding published main commit, then push only the assigned exact commit to main with a normal fast-forward. Do not push future increments, rewrite history, or alter timestamps. After a successful push, record the outcome. If missing or unsafe, report the blocker without publishing. Stop after the eighth release.

The active chat automation is named “AttendLog eight Friday releases”. It requires the laptop and desktop app to be running with network and repository access.
