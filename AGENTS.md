# AttendLog project rules

- Canonical checkout: `/Users/anishdangol/Documents/attend-log`.
- Read `assets/instructions.txt` and `docs/BUILD_PLAN.md` before implementation.
- User rule: preserve the supplied design and colors exactly. Do not redesign, replace the palette, change typography, or substitute a component library's default appearance.
- Palette reference: `assets/ui/color-reference.png`; preserve the five exact hex values in `attendlog/static/css/site.css`.
- Main visual reference: `assets/ui/landing pg ui.png`. The screenshot combines the three HTML references; do not replace it with any single HTML variant. Use the HTML references for original CSS values and corresponding component details. Ask about unresolved visual differences before changing the supplied design.
- Keep reference assets and the source ZIP unchanged. Do not import the ZIP's embedded `.git` directory, configuration, or hooks.
- The behavioral requirements in instructions.txt take priority over contradictory demonstration copy in the HTML. Record process conflicts and proposed resolutions in the build plan; do not silently change requirements.
- New screens must reuse the supplied visual language. Responsive layouts must preserve its palette and styling. New dark/light themes are deferred.
- Use the Incremental Model and verify each working increment. Do not build later-phase features before the core flow works.
- Students may access only their own data; teachers only assigned classes; administrators use their defined management permissions. Enforce this on the server.
- Never commit passwords, tokens, environment secrets, real face images/encodings, OTPs, session values, or personal student data. Use synthetic test fixtures and gitignored runtime storage.
- Git identity for this checkout is Anushma Shakya / 149258506+Namelessyus@users.noreply.github.com. The remote uses github-namelessyus.
- Commit actual completed work at its real timestamp. Scheduled Friday work must perform real reviews, tests, fixes, or useful documentation. Never use empty commits, fabricated progress, date overrides, or hold completed work to imply later development.
