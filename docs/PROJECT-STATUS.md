# Project status and handoff

**Checkpoint: 4 October 2026, Asia/Manila — initial Libre source preview.** “Implemented” means present in code; external account/terminal verification is called out separately. Earlier local checkpoints remain recorded in CHANGELOG.

## Repository and current state

- Public source repository: [npcagomoc-del/libre-trading-journal](https://github.com/npcagomoc-del/libre-trading-journal). The app is at the root of a fresh clone. [Windows installation](INSTALL-WINDOWS.md) covers downloading and running it on another PC.
- Original development app: `Trading-Journal-AI/`, inside the separately versioned `Trading Journal App` workspace. The upstream base is `631c574` — `Bump the frontend group in /frontend with 6 updates (#10)` (2026-09-18).
- Source publication is prepared in a separate checkout, preserving the original working tree and upstream history. It excludes runtime databases, uploads, credentials, generated dependencies, outputs, and unreviewed design drafts. Run `git status --short` for the current state of your own checkout.
- Initial source commit `8db2b70` was pushed to the public Libre `main` branch. GitHub identifies the repository as public and MIT licensed. Private vulnerability reporting is enabled. Hosted CI is checked separately from local results.
- Existing upstream docs/screenshots remain. Screenshots show the upstream synthetic demo and can differ from the current local branding/features.
- This feature pass adds Libre branding, AI selection and built-in backup/restore, with guides and future-AI instructions updated. Real journal data, existing credentials and Git history were preserved. Three Astra agents handled provider backend, backup backend and UI/design; parent integrated and checked the result.

## Implemented capabilities

| Area | Present behavior / evidence |
|---|---|
| Core journal | React UI, local FastAPI API, SQLite accounts/trades/diary/settings; dashboard, trade view/detail, calendar, reports, manual records and notes. `App.js`, `main.py`, `database.py`. |
| Existing imports | Thinkorswim, IBKR and generic fill CSV; grouping/reimport regression tests in `backend/tests/`. |
| Multi-asset local additions | Crypto, forex and gold types, fractional sizes, contract multipliers, explicit non-USD quote conversion; preserving migration and tests. |
| Exness local additions | Fully closed ticket CSV, broker-profit authority, signed charges/swaps, currency conversion, same-account ticket updates and notes preservation; parser and tests. |
| AI choices | ChatGPT sign-in preserved; added OpenAI API, direct Claude API and OpenRouter. Shared explicit selection across Brain/diary/insights/reviews, masked keys, model suggestions/manual IDs, billed test, no provider fallback. `ai_provider.py`, `ai_credentials.py`, `ai_provider_routes.py`, `AIProviderSettings.js`. The user reports ChatGPT works; no fresh live inference in this pass. |
| Backup/restore | Versioned ZIP with consistent SQLite snapshot + uploads, check/count preview, exact RESTORE confirmation, automatic pre-restore recovery and rollback. Strict path/schema/settings/checksum validation; credential stores excluded. Request draining coordinates one backend process. Tests use synthetic journals. |
| MT5 local additions | Python terminal and local MCP transports, per-journal-account identity checks, encrypted MCP key, clock-aware chart data for forex/gold/supported crypto; mocked tests pass. |
| UI local additions | Libre Trading Journal header/title, existing Happy Bull mascot, provider/backup controls, Brain status and original simonro credit in Settings. Isolated browser design/workflow check; no mobile browser walkthrough or claim of release approval. |
| Documentation | Workspace entry points, app AI instructions, user/developer/data/troubleshooting guides, decisions and evidenced change history. |

## Verification performed in this feature pass

| Check | Result |
|---|---|
| Backend tests with existing repo virtualenv | `.\.venv\Scripts\python.exe -m pytest backend/tests -q` — **154 passed**. Includes 32 focused backup tests and provider regressions. |
| Fresh backend dependency installation | All requirements installed in a new temporary Windows virtualenv on Python 3.12.10; **158 tests passed** with `.env` loading disabled and synthetic test stores. Four added MT5 request-validation cases prevent credential echo in 422 errors. |
| HEIC codec smoke check | Fresh-installed Pillow/pillow-heif encoded a synthetic HEIC image, decoded it, and converted it to a readable JPEG. Actual phone images/upload/inference were not tested in this check. |
| Frontend tests with installed dependencies | `CI=true`, `node node_modules/@craco/craco/dist/bin/craco.js test --watchAll=false --runInBand` from `frontend/` — **6 suites, 41 tests passed**. Includes structured provider-error display. |
| Production compilation | `CI=true`, `node node_modules/@craco/craco/dist/bin/craco.js build` — **compiled successfully**; Node `fs.F_OK` deprecation notice only. |
| Clean publication frontend install/checks | `npm.cmd ci --no-audit --no-fund` installed 1,381 packages into the separate publication checkout. `CI=true`, `npm.cmd test -- --watchAll=false --runInBand`: **6 suites / 41 tests passed**; `npm.cmd run build`: **compiled successfully**. Existing CRA-related dependency deprecations and Node `fs.F_OK` notice were non-fatal. |
| Runtime versions | Existing virtualenv Python **3.12.10**; bundled Node **24.19.0**. |
| Standard npm command | `npm.cmd` absent from this Codex shell's PATH; publication checks used the installed `C:\Program Files\nodejs\npm.cmd` (npm 11.17.0, Node 24.19.0). The user's destination PC still needs Node/npm installed and on PATH. |
| Publication scans/package | Allowlisted 129 source files, including 119 text files; the only custom token-pattern match was the explicitly synthetic test fixture. Gitleaks reported no leaks in the publication history. Source ZIP contents matched the allowlist exactly; no databases, credentials or uploaded journal files are included. |
| Hosted source CI | Public `main` at `0765a3e`: Windows backend, Linux backend, and frontend build/tests all passed. See [the completed CI run](https://github.com/npcagomoc-del/libre-trading-journal/actions/runs/37143035396). Subsequent documentation-only revisions do not establish new live provider/device coverage. |
| Source and history review | Read launch/setup scripts, requirements/package/CI, routes/schema/parsers, UI, existing docs, Git log and working-tree changes. |
| Browser/temporary runtime | Production UI at 3020 pointed only to disposable backend 8020; synthetic account/trade/diary/attachment, isolated credential/recovery paths and disabled .env loading. Checked provider selection, backup preview/restore/recovery and Brain setup navigation. Existing real servers/data were untouched. |
| Backup download | UI showed download initiation; synthetic API export returned a valid ZIP with zero missing attachments. Browser automation did not return the Blob-download path, so API output was used for the file-picker restore check. |
| Documentation checks | Publication review covers 15 Markdown files, checking local file links and heading anchors, shell-specific setup/update commands, upstream attribution and source-preview limits. `git diff --check` passed; CRLF normalization warnings only. |

No second physical PC installation, live ChatGPT/API login/inference, real MT5/Alpaca connection, real trade import or restore into the user's journal was performed. Tests use synthetic data and mocked external services. Provider transport tests cover request formats/images and error handling; actual API-key model access remains to be verified by the user in Settings. A passing build is not proof of external account access. Fresh backend tests emitted a non-failing Starlette TestClient/httpx deprecation warning.

## Known limitations and concrete follow-ups

These are observed code behavior or source-review findings, including pre-existing limitations outside this feature scope.

1. **Startup is sensitive to current directory and PATH.** Relative database/upload paths can produce a seemingly empty journal if launched elsewhere. Existing batch launch/setup also depend on Python/npm command discovery. Manual startup and bundled-Node fallback are documented.
2. **HEIC image coverage is limited.** Pillow/pillow-heif are included in requirements, and a synthetic codec smoke check passed. Real device images and the full HEIC upload/inference workflow remain unverified. Export JPEG/PNG if conversion fails.
3. **CSV writes are not universally atomic after parsing.** Parsing errors precede writes, but individual database-write errors can be collected while other rows commit. A future change should decide/report transaction semantics clearly.
4. **KPI definitions differ.** `/api/kpis` includes all selected records in trade win-rate counts, uses gross P&L grouped by net win/loss for profit factor, and its strategy subquery omits date bounds. Documented in DATA-GUIDE; add expected-value/date-boundary tests before changing behavior.
5. **Stock chart clock/proxy limitations.** Alpaca intraday query uses a fixed `-04:00` session offset; winter dates deserve a timezone review. Futures can be ETF proxies. MT5 historical offsets are manually selected and need correct source clocks.
6. **Blank custom Alpaca feed configuration.** `.env.example` now specifies `ALPACA_DATA_FEED=iex`. A manually blank value still bypasses the `os.getenv` default; use explicit `iex` or omit the line.
7. **Diary recovery/persistence gaps.** Upload saves before AI analysis; failure leaves a record with no dedicated retry button. Reuploads create more records; deleting records leaves uploaded files. Brain conversation is not persisted.
8. **Credential portability.** Windows DPAPI stores require the same Windows security context; reconnect after moves. Non-Windows ChatGPT storage lacks DPAPI; MT5 MCP encrypted keys currently require Windows. Cross-platform parity is unverified.
9. **Migration diagnostics.** Additive migrations catch broad exceptions. A schema error may require targeted investigation; do not assume a successful server response proves every optional column migration worked.
10. **Local-only scope.** Ordinary journal routes are not a multi-user authenticated service. Keep loopback startup; this is not a deployment-ready shared server. The OneDrive checkout introduces filesystem synchronization outside the app's own behavior.
11. **Backup compatibility/coordination.** Current schema only, conservative supported settings/uploads, documented archive limits and one backend process. Unknown schemas fail rather than lose data. External SQLite tools/OneDrive are outside the maintenance gate. Missing attachments in incoming or current recovery snapshots block restore. Scheduled backups are not configured.
12. **API model access and image support.** Provider catalogs/permissions change. Manual OpenRouter models need catalog refresh for image capabilities; text-only models cannot analyze screenshots. API use is separately billed. Saved/cached review content is not regenerated just because the provider changes.

## Unfinished / next useful steps

Recommended sequence, not a claim of earlier user commitments:

1. Use the documented manual startup in the user's normal terminal if launch still fails; capture the exact first error and distinguish frontend/backend/PATH issues.
2. With user-authorized external usage, complete **Test connection** for ChatGPT and **Connect & test MT5**, then compare a known historical trade's chart clock/symbol. Record live results without secrets.
3. Reconcile a small redacted/synthetic Exness file and a corrected/repeated import in a disposable account/database before broad importer changes. Existing unit tests provide a starting point.
4. Review the KPI/transaction/config findings above and prioritize fixes with tests. Do not silently redefine historical metrics.
5. The disposable backup/restore check is complete. Establish a backup routine and consider compatibility/retention work deliberately; no schedule is configured.
6. Download the source onto the destination PC using INSTALL-WINDOWS, then follow its empty-journal setup or privately transfer a journal backup. Reconnect installation-specific credentials there.

## Continue from here

Read [AGENTS.md](../AGENTS.md), then [developer guide](DEVELOPER-GUIDE.md). Provider work requires [AI-PROVIDERS.md](AI-PROVIDERS.md); backup work requires [BACKUP-RESTORE.md](BACKUP-RESTORE.md). For a user issue start with [troubleshooting](TROUBLESHOOTING.md). Before touching persisted records, read [data guide](DATA-GUIDE.md). Update this checkpoint with actual new evidence; do not turn an unverified capability into a completed claim.
