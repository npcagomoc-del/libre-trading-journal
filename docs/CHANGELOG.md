# Evidenced change history

This file separates upstream commits from the local working tree. Dates below describe visible Git history or this documentation checkpoint. Earlier chat history was not available to the author and is not reconstructed.

## 2026-10-04 — initial Libre source preview

- Prepared source for `npcagomoc-del/libre-trading-journal` in a separate checkout, retaining upstream history and the original Tape to Edge MIT copyright. Runtime journal data, uploaded files, credentials and unreviewed design drafts are excluded.
- Added Windows download/setup tutorial, portable repository paths, Libre source/CI links, and Linux/Windows backend CI checks.
- Added Pillow/pillow-heif to backend requirements and explicit `iex` to the Alpaca template. A synthetic HEIC-to-JPEG codec smoke check passed in a fresh Windows virtualenv.
- Sanitized MT5 request-validation errors so malformed requests do not echo credential inputs. Four regression cases increased the full backend suite to **158 passing tests** after installing all requirements into a clean virtualenv.
- Clean `npm ci` installation in the separate publication checkout also passed **41 tests / 6 suites** and the CI-mode production build. External AI/model access and real journal transfers are not certified by these checks.
- Published the source preview on the user's `npcagomoc-del` GitHub account. Public repository/branch and MIT detection were verified; private vulnerability reporting is enabled. Gitleaks found no leaks in the publication history; the 129-file source ZIP matches its allowlist.

## 2026-10-04 — Libre AI choices and backup/restore (uncommitted)

- Added explicit ChatGPT sign-in, OpenAI API key, direct Claude API key and OpenRouter API key choices, shared across Brain/diary/insights/reviews. Existing ChatGPT OAuth and connection storage retained.
- Added protected installation key storage, masked/cleared key forms, model discovery/manual IDs, explicit billed connection test and sanitized errors; no automatic provider fallback. Image conversion/capability handling covered by transport tests.
- Added consistent SQLite + attachment ZIP exports, inspection/count preview, exact RESTORE confirmation, automatic recovery copies/downloads, rollback and request coordination. Validation rejects unsafe/incompatible archives and excludes service credentials. Missing incoming/current recovery attachments block restore.
- Added Libre name in header/public metadata/API title, Brain provider status and original Simon / simonro attribution in Settings/README; original MIT license retained.
- Added provider/backup tutorials and updated user, developer, data, troubleshooting, status and AI handoff instructions.
- Checks: **154 backend tests**, **41 frontend tests / 6 suites**, successful CI production build. Isolated browser check used synthetic data and separate credentials/recovery paths; no real restore or live paid inference. See PROJECT-STATUS for exact evidence limits.
- Three user-requested Astra agents assisted with backend and UI/design. No commit, push or publication performed.

## 2026-10-03 — local documentation checkpoint (uncommitted)

- Added user tutorial, startup/error recovery, developer architecture/setup/checks, data/backup/restore, status and decisions guides.
- Added future-AI reading order and preservation rules in app `AGENTS.md`, with workspace entry points for the nested repository.
- Updated README navigation and corrected backup/update/setup explanations for this local version while retaining existing feature sections and upstream attribution.
- Verified existing code with 93 backend tests, 28 frontend tests across 4 suites, and a successful CI-mode production build. Used installed CRACO directly because npm was absent from this Codex shell's PATH.
- Documentation work does not create an application release or certify live external connections. No commit/push was made.

## Local feature changes already present at the checkpoint (unreleased)

These are evidenced by modified/untracked files relative to app HEAD `631c574`; exact development order and earlier verification are not asserted.

- Crypto/forex/gold instrument types, fractional sizing, multiplier/conversion fields and preserving database migration (`instruments.py`, `database.py`, `csv_parser.py`, manual trade UI and tests).
- Exness closed-position CSV parser, templates, ticket-based repeat/corrected imports, broker profit/fees/swaps and tests (`exness_parser.py`, `main.py`, Import UI).
- ChatGPT plan connection/provider/routes/UI, shared coaching calls, encrypted Windows credentials and mocked regression tests.
- MT5 Python and MCP market data, account-specific connection UI, identity checks, historical clocks, encrypted MCP keys and tests.
- Happy Bull branding/assets and navigation/style adjustments.

Use `git diff` plus untracked-file review to inspect these changes. A tracked-file diff alone omits newly added modules/assets/tests. Do not label them upstream releases.

## Selected upstream commits visible locally

| Date (Git author date) | Commit | Recorded change |
|---|---|---|
| 2026-09-18 | `631c574` | Frontend dependency group update (#10); inspected HEAD. |
| 2026-09-18 | `60b9058` | Backend dependency group update (#7). |
| 2026-09-18 | `3345d83` | CI uses Node 24; grouped weekly dependency updates. |
| 2026-09-18 | `4a2603d` | Launcher starts backend with `python -m uvicorn`. |
| 2026-09-18 | `60d8628` | New installs start empty; demo seed avoids overwriting a database. |
| 2026-09-18 | `054c37c` | Thinkorswim/IBKR parser tests against supplied samples. |
| 2026-09-18 | `6bea9ec` | Contributing guide, code of conduct and issue/PR templates. |
| 2026-09-17 | `e6bbaf1` | Privacy/data-handling documentation. |
| 2026-09-15 | `dbdd4ea` | Prevent a repeat import from overwriting a stored trade of the same name. |
| 2026-09-14 | `b220883` | Day Review measures, including exit efficiency and averages. |
| 2026-09-13 | `769e345` | Generic broker CSV template/example support. |

This is a selected history, not every change. Reproduce locally with `git log --date=short --format="%h %ad %s"` from the app repository. Future entries should describe what actually changed, its validation, and unresolved limits.
