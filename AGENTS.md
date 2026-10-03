# Instructions for future AI collaborators

## Read first

1. `docs/PROJECT-STATUS.md`: current implementation, checks, limitations, next steps.
2. `README.md` and `docs/DEVELOPER-GUIDE.md`: entry points, setup and architecture.
3. `docs/DATA-GUIDE.md` before imports, money, schema, backup or restore work.
4. `docs/TROUBLESHOOTING.md` for failures; `docs/USER-GUIDE.md` for current UI workflows.
5. `docs/DECISIONS.md`, `docs/CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` as relevant.

These documents describe inspected code, not hidden conversation history. Verify current code and `git status --short` before acting. Preserve existing user changes; never reset, clean, stash, overwrite or commit unrelated work without authorization. The original development checkout is nested inside a separately versioned workspace; a fresh Libre clone has the app at its root. Check your Git root.

## Working rules

- Use the repo's `.venv/Scripts/python.exe` on Windows or `.venv/bin/python` on macOS/Linux. For runtime, set working directory to `backend/`; default database and upload paths are relative to it. UI runs in `frontend/` on port 3010; backend on loopback port 8010. ChatGPT callback is fixed to 8010.
- Keep trade grouping, USD money calculations, fee signs, multipliers, currency conversion and duplicate handling deterministic. Changes need worked expected values and meaningful regression tests. Preserve account-scoped Exness tickets and notes/tags on corrected imports.
- Never use the user's live database for tests, seed demo data into it, delete it to fix startup, or print real trades/credentials. Use temporary databases and synthetic fixtures. Do not read `.env`, OAuth token files or encrypted MT5 keys merely to inspect setup.
- Take a consistent backup before an authorized migration/data repair. SQLite uses WAL. Include diary uploads, and preserve the previous database when restoring. Follow `docs/DATA-GUIDE.md`.
- AI is optional. Read docs/AI-PROVIDERS.md: ai_provider.py dispatches explicitly to ChatGPT plan OAuth, OpenAI API, Anthropic API, or OpenRouter. Preserve existing OAuth, localhost guards, request headers, completed-response checks and separate installation credential storage. Never automatically fall back to another provider/key or claim API usage is included in a ChatGPT subscription. Tests must isolate both provider and ChatGPT stores. Do not test live inference or sign-in unless it is in the user's requested scope.
- Backup/restore requires docs/BACKUP-RESTORE.md. Archives contain journal data and uploads, never credentials or .env. Preserve validation, exclusive maintenance gating, pre-restore recovery copies and rollback. Test only disposable databases/uploads; never restore a test archive into the real journal. Use one backend process for this local app.
- Product name is Libre Trading Journal. Credit Simon / simonro / Tape to Edge and link the original Trading-Journal-AI in release documentation and About/Settings; preserve the original MIT copyright and license. Publishing is a separate action from local development.
- MT5 integration reads account identity and candles; it must not place trades. Preserve account checks, localhost MCP restrictions, credential separation and explicit historical clock offsets. Do not replace missing market data with invented candles.
- Keep the app bound to localhost. Do not add cloud services, telemetry, deployment, paid services or external communications as incidental changes.
- Make narrow changes. Update the applicable guide and status checkpoint when behavior changes. Distinguish code inspection, automated tests and live end-to-end verification; do not call a feature verified just because its mocked tests pass.

## Checks

From app root: `.\.venv\Scripts\python.exe -m pytest backend/tests -q`.
From `frontend/`: `npm.cmd test -- --watchAll=false --runInBand`, then `npm.cmd run build` with `CI=true` for CI-equivalent lint enforcement. See the developer guide for a bundled-Node fallback when npm is absent. Choose checks appropriate to the change; do not install dependencies or repeat full suites unnecessarily.

On macOS/Linux use `.venv/bin/python -m pytest backend/tests -q` from app root and `CI=true npm test -- --watchAll=false --runInBand`, then `CI=true npm run build` from `frontend/`.

Report changed files, actual commands/results, unresolved failures and anything not tested. Update `docs/CHANGELOG.md` with evidenced changes, keeping uncommitted local work separate from upstream commit history. Do not infer release status, completed live connections or user decisions that the evidence does not establish.
