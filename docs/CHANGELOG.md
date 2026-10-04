# Changelog

Changes below are recorded from Git history, source review and test results. The earlier local-development entries describe the work before publication.

## 2026-10-04 — repository preview and publication checks

- Updated the README with the current features and screenshots captured from the actual application. Six wholly fictional trades in a disposable journal demonstrate source/PHT times, midnight rollover and session performance; screenshots do not use personal journal values.
- Retained original MT5 setup footage with opaque privacy masks and removed the later private trading-history section from the public excerpt. No generated instruction cards are used. The original recording remains private and unchanged.
- Corrected the dashboard headline's dollar/cents formatting: $41.60 no longer appears as $42.60. Stored P&L calculations are unchanged; regression cases include negative cents, sub-dollar losses and rounding carry.
- Fresh local checks: 183 backend tests and 9 frontend suites / 58 tests passed; production build passed. Publishing uses the separate Libre repository checkout, a source allowlist, redacted secret scans and required hosted CI; runtime journals, uploads, credentials and raw recordings are excluded. The public video passed 2,080 sensitive-region frame checks, full decoding and visual transition review.

## 2026-10-04 — Settings guides, dashboard calendar and private MT5 walkthrough (implementation checkpoint)

- Fixed the dashboard date picker clipping at the hero boundary. Its portal stays within the viewport, scrolls when needed, and preserves presets, outside-click and Escape dismissal.
- Simplified AI settings labels and removed redundant capability badges. Added numbered MT5 and backup/restore guides, explicitly stating MT5 must stay open and connected while charts load. Existing connection checks and restore safeguards remain.
- Embedded a 24-second real MT5 setup excerpt with controls, optional captions, a redacted actual screenshot preview and no autoplay. The 446,968-byte public file masks MCP keys, account identity, browser download history and transition previews. Audio and the later private trade-history section are excluded. The original recording is untouched.
- Astra assisted with Settings design and implementation. Validation: 8 frontend suites / 54 tests passed; after the original-footage revision, 5 focused MT5 tests passed and the CI production build compiled successfully. Synthetic localhost browser checks verified calendar viewport bounds, Settings guides and actual video playback. Privacy review covered one frame per second throughout, the key region across the MT5 segment and complete video decoding. No live MT5 connection or journal restore was performed. Public updates use the repository's required pull-request and CI workflow.

## 2026-10-04 — simpler time controls and paired entry hours (implementation checkpoint)

- Put original entry half-hour labels beside Philippine time in Dashboard Patterns and Reports Timing. Labels come from the actual entries, including rollover, mixed source clocks and historical DST.
- Added an Exness UTC+0 source caption beside Philippine time UTC+8, with per-entry labels for mixed source clocks. Reduced visible clock settings to that compact caption and an optional adjustment disclosure. Session-hour explanations are collapsed. Automatic conversion remains the default; manual overrides remain visible and resettable.
- Preserved the previous clock/session feature, original records and existing working-tree changes. Validation: 183 backend tests, 7 frontend suites / 50 tests, and CI production build passed. Synthetic browser checks covered paired hours, captions, the optional adjustment and override reset. Included in the repository update after local validation.

## 2026-10-04 — Philippine entry time and trading sessions (implementation checkpoint)

- Added derived Philippine entry date/time and session columns, preserving source timestamps and closing-date filters.
- Added full-day Philippine half-hour performance and disjoint market-session/overlap performance on Dashboard Patterns and Reports Timing, with trades, win rate, average and net P&L.
- Added a shared browser source-clock selector, explicit unclassified records, historical DST handling and the tzdata backend dependency. Original import/money calculations and chart clocks are unchanged.
- Backend: 180 tests passed, including 22 new clock/analytics/API regressions on synthetic data. Frontend: 7 suites / 45 tests passed; CI production build compiled successfully. Synthetic desktop browser checks covered rows, Dashboard, Reports and shared source-clock conversion; screenshots and details are recorded in PROJECT-STATUS. This records the initial feature-validation checkpoint; the later repository update includes these changes.

## 2026-10-04 — product name and documentation wording

- Replaced shortened product names with Libre Trading Journal throughout the public documentation.
- Rewrote the installation/repair prompts and simplified README wording. Added the full-name convention to AGENTS.md.
- Documentation-only change. Checked links, heading anchors and whitespace; no application behavior changed.

## 2026-10-04 — AI-assisted installation prompts

- Added copy-and-paste prompts for an AI coding assistant to install/start Libre Trading Journal and diagnose startup errors on the user's own PC.
- Covered missing prerequisites, shell-specific commands, durable server sessions, health/browser evidence, existing-journal preservation and necessary human installer actions. Optional AI credentials and paid inference remain separate from installation.
- Linked the prompts prominently from README and the Windows tutorial. Documentation-only change; prompts were checked against repository guides, not executed as a fresh installation on a second PC.

## 2026-10-04 — public documentation polish

- Separated Windows PowerShell and macOS/Linux commands in README/CONTRIBUTING; documented the untested macOS scope and Windows-only MT5 integration.
- Updated safe Git/ZIP update instructions to use the app interpreter, committed frontend lockfile, and built-in backup/restore.
- Shortened the introductory Exness section, clarified current Settings controls, and replaced inherited first-person creator/affiliate wording with explicit Simon attribution and Libre Trading Journal maintainer links.
- Made AI contributor commands portable, linked the importer prompt to AGENTS/data safeguards, and removed checkout-specific wording from generic setup/data guidance.
- No application behavior changed. Hosted CI for source commit `0765a3e` passed Windows/Linux backend and frontend checks. Documentation is validated with local link/anchor and whitespace checks rather than rerunning application tests locally.

## 2026-10-04 — initial Libre Trading Journal source preview

- Prepared source for `npcagomoc-del/libre-trading-journal` in a separate checkout, retaining upstream history and the original Tape to Edge MIT copyright. Runtime journal data, uploaded files, credentials and unreviewed design drafts are excluded.
- Added Windows download/setup tutorial, portable repository paths, Libre Trading Journal source/CI links, and Linux/Windows backend CI checks.
- Added Pillow/pillow-heif to backend requirements and explicit `iex` to the Alpaca template. A synthetic HEIC-to-JPEG codec smoke check passed in a fresh Windows virtualenv.
- Sanitized MT5 request-validation errors so malformed requests do not echo credential inputs. Four regression cases increased the full backend suite to **158 passing tests** after installing all requirements into a clean virtualenv.
- Clean `npm ci` installation in the separate publication checkout also passed **41 tests / 6 suites** and the CI-mode production build. External AI/model access and real journal transfers are not certified by these checks.
- Published the source preview on the user's `npcagomoc-del` GitHub account. Public repository/branch and MIT detection were verified; private vulnerability reporting is enabled. Gitleaks found no leaks in the publication history; the 129-file source ZIP matches its allowlist.

## 2026-10-04 — Libre Trading Journal AI choices and backup/restore (uncommitted)

- Added explicit ChatGPT sign-in, OpenAI API key, direct Claude API key and OpenRouter API key choices, shared across Brain/diary/insights/reviews. Existing ChatGPT OAuth and connection storage retained.
- Added protected installation key storage, masked/cleared key forms, model discovery/manual IDs, explicit billed connection test and sanitized errors; no automatic provider fallback. Image conversion/capability handling covered by transport tests.
- Added consistent SQLite + attachment ZIP exports, inspection/count preview, exact RESTORE confirmation, automatic recovery copies/downloads, rollback and request coordination. Validation rejects unsafe/incompatible archives and excludes service credentials. Missing incoming/current recovery attachments block restore.
- Added Libre Trading Journal name in header/public metadata/API title, Brain provider status and original Simon / simonro attribution in Settings/README; original MIT license retained.
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
