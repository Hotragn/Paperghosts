# Resume

Where the build stands, for whoever picks it up next. The spec is `BRIEF.md`, and the reasons behind each choice are in `DECISIONS.md`. Each step ends with a STATUS block below.

## Next step

**Step 1: setup and archive read.**

Hard date: the site must be live on Oct 31, so Steps 1–5 need to fit in about 33 hours.

Already done (Oct 29):
- The private GitHub repo `Hotragn/Paperghosts` is cloned here; its only commit so far is the LICENSE.
- `.gitignore` covers `.env` and keeps `Docs/IDEAS.md` private.
- `.env` holds the keys copied from Week 3 (never displayed).
- Entire session capture is enabled for Claude Code in this repo only. Checkpoints sync to `origin` on push.

Sentry is ready (done Oct 29):
- Projects `paperghosts-api` (Python/FastAPI) and `paperghosts-web` (React) exist in org `hotragn`.
- Their DSNs are in `.env` as `SENTRY_DSN` and `SENTRY_DSN_WEB`. These replaced the old Flare DSN.
- An auth token with read access is in `.env`.
- The GitHub repo is linked in Sentry.
- Wire the SDKs as the code appears.

The build waits on no one. Optional extras that the owner may add later:
- Ultramarine key and SerpApi key (they upgrade Step 4)

Needs the owner's yes when we get there:
- Render deploy
- domain DNS
