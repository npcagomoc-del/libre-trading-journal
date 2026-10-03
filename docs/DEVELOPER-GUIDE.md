# Developer guide

Scope: the Libre source preview prepared on **2026-10-04**. Start with [project status](PROJECT-STATUS.md); follow [AGENTS.md](../AGENTS.md) when using an AI collaborator. Contribution procedures are in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Locate the correct repository

```powershell
Set-Location -LiteralPath 'C:\Projects\libre-trading-journal'
git rev-parse --show-toplevel
git status --short
```

All paths in this guide are relative to the **app repository root** unless stated otherwise. A fresh Libre clone is already that root. The original development workspace nests `Trading-Journal-AI` inside a separately versioned `Trading Journal App` folder; preserve both repositories when working there.

## Setup on Windows

Repository setup requires Python 3.11+ and Node.js/npm. CI uses Python 3.11 and Node 24. A fresh temporary Windows virtual environment on Python 3.12.10 installed every backend requirement and passed 158 backend tests. This does not establish installation on a second physical PC. See [Windows installation](INSTALL-WINDOWS.md) for the download workflow and [project status](PROJECT-STATUS.md) for frontend checks.

1. Install Python and Node.js with npm if absent; open a fresh terminal afterward.
2. Run `.\setup.bat` from app root. It creates/reuses `.venv`, installs `backend/requirements.txt`, runs `npm ci` (with `npm install` fallback), and creates `backend/.env` only when missing.
3. Inspect any errors before proceeding. Configure AI in Settings using ChatGPT sign-in or the selected API provider; AI keys are not read from `.env`. `.env` is for optional market data and advanced local path/configuration overrides.

Manual PowerShell equivalent, from app root:

```powershell
python --version
node --version
npm.cmd --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Push-Location frontend
npm.cmd ci
Pop-Location
if (-not (Test-Path -LiteralPath 'backend\.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination 'backend\.env'
}
```

Run commands one at a time and stop at a failure. Calling the virtualenv interpreter directly avoids PowerShell activation-policy problems. `npm.cmd` avoids `npm.ps1` execution-policy errors on standard Windows Node installations. If neither npm nor npm.cmd exists, see the troubleshooting guide; do not assume that an available `node.exe` includes npm on PATH.

## Run and stop

For ordinary use: `.\launch.bat`, then open [http://localhost:3010](http://localhost:3010). For clear logs, use two PowerShell terminals:

**Backend terminal**

```powershell
Set-Location -LiteralPath 'C:\Projects\libre-trading-journal\backend'
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8010
```

**Frontend terminal**

```powershell
Set-Location -LiteralPath 'C:\Projects\libre-trading-journal\frontend'
$env:PORT = '3010'
npm.cmd start
```

Press Ctrl+C in each terminal to stop it. The frontend development server and Python backend are separate processes; a successful UI build does not start either server.

Read-only health check from a third terminal:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8010/' -TimeoutSec 5
```

Expected: `status` is `ok`. [FastAPI API docs](http://127.0.0.1:8010/docs) expose routes while the server runs; avoid executing mutation endpoints against real data while exploring. The health endpoint checks that the app responds, not that external connections work or journal contents are correct.

**Working directory matters:** `DATABASE_PATH` defaults to `trading_journal.db`, and `UPLOAD_DIR` to `uploads`, both relative to the backend process working directory. Starting incorrectly can create an empty database in another directory. Use the backend directory above rather than improvising a module command at workspace root.

The frontend may offer a different port when 3010 is busy. Prefer finding the existing server first. Local CORS permits other localhost ports, but the ChatGPT callback is hard-coded to `http://127.0.0.1:8010/auth/callback` and its return link to frontend 3010. Keep backend 8010 for sign-in.

## Configuration reference

| Setting | Location / meaning |
|---|---|
| `DATABASE_PATH` | Backend environment/`.env`; default relative `trading_journal.db`. Prefer an absolute path for an intentional relocation. |
| `UPLOAD_DIR` | Backend environment/`.env`; default relative `uploads`. Create its parent directories if overriding. |
| `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY` | Optional Alpaca credentials in `backend/.env`; restart backend after changes. |
| `ALPACA_DATA_FEED` | Code default is `iex` if absent. An empty assignment is an empty value; explicitly use `iex` or omit the line. |
| `FRONTEND_ORIGINS` | Comma-separated extra CORS origins for ordinary routes. Does not bypass local-only AI/MT5 checks. |
| `REACT_APP_API_URL` | Frontend process environment or frontend `.env`; default `http://localhost:8010`. Restart frontend after changing. Never put secrets in a `REACT_APP_` variable. |
| `PORT` | Frontend dev-server port; launcher sets 3010. |
| AI provider/key/model | Settings UI; shared selection for all AI features. ChatGPT OAuth stays in its original store; API keys and selection use a separate Windows DPAPI store outside the checkout. See [provider guide](AI-PROVIDERS.md). |
| MT5 feed per account | Settings UI; configuration in database, encrypted MCP key outside checkout. |

Do not print or commit real `.env` contents, broker files, databases, tokens or access keys. [Data guide](DATA-GUIDE.md) documents actual paths and portability.

## Architecture and source map

```text
Browser: React 19 + CRACO/CRA, localhost:3010
  frontend/src/App.js (page state and account selection)
  frontend/src/api.js (Axios, API URL, X-Journal-Request header)
        |
FastAPI/Uvicorn: backend/main.py, loopback:8010
  |-- database.py / library.py -> SQLite + WAL
  |-- csv_parser.py / exness_parser.py / instruments.py -> deterministic imports
  |-- ai_analysis.py / daily_summary.py -> ai_provider.py -> selected AI service
  |-- journal_maintenance.py -> backup_routes.py / journal_backup.py -> ZIP + recovery
  |-- mt5_routes.py -> mt5_market_data.py / mt5_mcp.py -> local terminal
  |-- chart endpoint -> optional Alpaca stock bars
  `-- uploads directory -> diary files served under /uploads
```

| Area | Source / responsibility |
|---|---|
| App shell/navigation | `frontend/src/App.js`, `components/AppHeader.js`; state-based pages, account selector, More menu, Brain drawer. |
| UI styling | `frontend/src/index.css`, `v3.css`, `v3/`; current logo in assets/public. |
| Import UI/templates | `components/Import.js`, `frontend/public/templates/`. |
| Trade edit/chart | `AddTradeModal.js`, `TradeDetail.js`, `TradingChart.js`. |
| Screens | Dashboard, Trades, Calendar, DailySummary, Reports, Diary, Settings, Help. Some component files are not directly navigable pages. |
| Database | `backend/database.py`: schema, connection settings, startup migrations; `library.py`: names and aliases. |
| Import/reimport | `csv_parser.py`: broker registry, generic/TOS/IBKR normalization, grouping/fingerprints; `exness_parser.py`: ticket-based closed positions. |
| Money/asset rules | `instruments.py`, parser aggregation, `main.py` manual P&L and execution edits. |
| AI auth | `chatgpt_routes.py`: local guards/OAuth routes; `chatgpt_provider.py`: PKCE, token storage/refresh, model list, completed-stream validation. |
| AI provider selection | `ai_provider_routes.py`, `ai_provider.py`, `ai_credentials.py`: explicit dispatch, model discovery, sanitized errors, separate installation credentials. `AIProviderSettings.js` supplies controls/status. |
| Backup/restore | `journal_backup.py`, `backup_routes.py`, `journal_maintenance.py`, `BackupRestore.js`: snapshot/validation, exclusive request draining, recovery and rollback. One backend process only; external database writers are outside the gate. See [backup guide](BACKUP-RESTORE.md). |
| AI features | `ai_analysis.py`, `daily_summary.py`, corresponding routes in `main.py`. |
| MT5 | `mt5_routes.py`: settings endpoints; `mt5_market_data.py`: Python terminal/candles; `mt5_mcp.py`: restricted read tools and encrypted key store. |
| Tests/CI | `backend/tests/`, frontend `*.test.js`, `.github/workflows/ci.yml`. |
| Synthetic development assets | `scripts/sample_import*.csv`, `scripts/seed_demo.py`, `scripts/demo_prices.json`. Never seed the user's journal. |

Startup initializes database/library tables and uploads. The multi-asset migration transactionally rebuilds the old instrument CHECK constraint while preserving IDs and creating a pre-migration SQLite backup. Other additive column migrations currently catch broad exceptions; investigate schema failures rather than assuming they all succeeded.

## Tests and validation

From app root, if pytest is not installed:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
```

Run backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

From `frontend/`:

```powershell
$env:CI = 'true'
npm.cmd test -- --watchAll=false --runInBand
npm.cmd run build
```

CI uses the equivalent CRACO test/build commands. `CI=true` makes production-build lint warnings fail. These commands use temporary/mock data in tests; review new fixtures before running unfamiliar changes.

**Existing-dependencies fallback used in this Codex shell:** node was available but npm/npx were not. With `frontend/node_modules` already installed, run from `frontend/`:

```powershell
$env:CI = 'true'
node node_modules/@craco/craco/dist/bin/craco.js test --watchAll=false --runInBand
node node_modules/@craco/craco/dist/bin/craco.js build
```

For startup in the same situation: set `$env:PORT='3010'`, then `node node_modules/@craco/craco/dist/bin/craco.js start`. This is not a dependency installation substitute; if the file is missing, restore npm and perform setup.

At the 4 October feature checkpoint: **154 backend tests passed; 6 frontend suites / 41 tests passed; production build compiled successfully.** A Node `fs.F_OK` deprecation warning was printed during the successful build. Tests isolate journal, credential and recovery stores. See [status](PROJECT-STATUS.md) for browser evidence and external-service verification limits.

## Extend or update safely

1. Read `git status`, compare the intended files, and preserve existing local changes. This checkout is not a clean upstream release.
2. Back up consistent database + uploads before an authorized update or migration. Preserve `.env` separately and reconnect external services if moving Windows user/machine.
3. Inspect upstream changes before merging them into this customized version. A blind `git pull` or ZIP overwrite can conflict with local feature work; do not use force/reset as an update procedure.
4. Install requirements with the repo interpreter when needed; use `npm ci` for the committed lockfile. Review dependency/lock changes rather than automatically accepting a generated replacement.
5. Test behavior with synthetic data and run the relevant full checks. Verify startup in a separate disposable database when changing initialization.
6. Update the status, changelog, affected user/data instructions and evidence limits.

For new broker importers, follow the registry/UI/test workflow in CONTRIBUTING, but account for the expanded asset fields and separate Exness position parser in this version. Do not force position rows into a fill parser. Schema/settings changes must deliberately update backup compatibility and tests. There is no scheduled backup, automated app update or production deployment configuration. Preserve Simon / simonro's MIT credit when preparing a Libre release; publication requires its own requested action.
