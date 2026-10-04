# Kapag ayaw mag-open: startup and error recovery

**Huwag munang mag-delete ng database o mag-reinstall.** Alamin muna kung alin ang hindi gumagana: backend, frontend, import, AI, o chart. Hindi kailangan ng ChatGPT o MT5 connection para mag-open ang journal at makita ang saved trades.

This guide matches local code updated on **2026-10-04**. Commands below are for Windows PowerShell. Run them in the named folder. Keep the first meaningful error message; later errors can be consequences of the first one.

## Start here when the app will not open

1. Open the app folder containing `setup.bat`, `backend`, and `frontend` — ito ang app folder, hindi ang parent folder. For a new PC, begin with [Windows installation](INSTALL-WINDOWS.md).
2. If the two server windows are already open, inspect them before launching another copy. Normal startup needs both the Backend and Frontend processes.
3. Open [http://127.0.0.1:8010/](http://127.0.0.1:8010/). Expected text: `{"status":"ok"}`.
4. Open [http://localhost:3010](http://localhost:3010). This is the actual journal screen.
5. Use this table to choose the next step:

| What you see | What it means / next step |
|---|---|
| 8010 will not connect | Backend is stopped, failed startup, or using a different port. Start backend manually below and read its error. |
| 8010 says `ok`, 3010 will not connect | Backend works; frontend is stopped or failed compilation. Start frontend manually below. |
| 3010 opens, but requests fail / accounts never load | Check backend 8010 and frontend API URL; inspect browser Network errors. |
| Both respond, but your data is missing | Check selected account/date filters and the database path. **Do not reimport everything or create replacement accounts yet.** |
| Only AI or price chart fails | Follow the feature-specific sections. Your journal may still be saved and usable. |

### Manual start para makita ang totoong error

Open one PowerShell terminal for backend:

```powershell
Set-Location -LiteralPath 'C:\Projects\libre-trading-journal\backend'
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8010
```

Wait for **Application startup complete**. Leave it running. Open a second terminal for frontend:

```powershell
Set-Location -LiteralPath 'C:\Projects\libre-trading-journal\frontend'
$env:PORT = '3010'
npm.cmd start
```

Wait for successful compilation, then open localhost:3010. Kung may error, keep that terminal open and match it below. Use Ctrl+C in each terminal to stop deliberately. Do not close or stop unrelated Python/Node programs.

## Setup and command errors

| Error / symptom | Recovery |
|---|---|
| `python was not found`, Microsoft Store opens, or unsupported version | Install Python 3.11+ with PATH enabled, then reopen PowerShell. For an existing install use the project's `.venv\Scripts\python.exe`. |
| `.venv\Scripts\python.exe` does not exist | Run `setup.bat` from app root, or the [manual setup](DEVELOPER-GUIDE.md#setup-on-windows). Do not delete the database. |
| `No module named uvicorn`, `fastapi`, `jwt`, etc. | From app root run `.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt`; restart the backend using that same interpreter. |
| `Could not import module "main"` | Start from the `backend` directory using the exact command above. Read any preceding traceback for a missing dependency. |
| `npm` / `npm.cmd` not recognized | Install/repair Node.js with npm and reopen the terminal. `node --version` alone does not prove npm exists. The Codex shell in this session had bundled Node but no npm command. |
| `npm.ps1 cannot be loaded ... running scripts is disabled` | Use `npm.cmd` in place of `npm`. No global execution-policy change is required. |
| `craco` not recognized / missing `node_modules` | From `frontend`, run `npm.cmd ci`, then start again. Wait for installation to finish successfully. |
| `npm ci` reports lock/package mismatch or install failure | Read the first error. Use the expected Node version (CI: 24), confirm network access and available disk space. Preserve package files; do not automatically delete the lockfile. `setup.bat` can fall back to `npm install`, which may change it. Ask the maintainer/AI to review the exact mismatch if it persists. |
| `Activate.ps1` blocked | Use the virtualenv interpreter directly as above; activation is unnecessary. |
| Frontend says `Failed to compile` | Copy the first file/line error; fix that source/dependency issue or ask AI to do so. The browser refresh cannot repair a compiler error. |

If you are in Codex's shell, `node` is available, and the app's dependencies are already present, this frontend fallback works from `frontend/`:

```powershell
$env:PORT = '3010'
node node_modules/@craco/craco/dist/bin/craco.js start
```

If that file does not exist, setup is incomplete. Do not use this as a substitute for installing dependencies.

## Port is already in use

Typical backend errors include `WinError 10048` or “address already in use.” The frontend may say another process is running on 3010.

1. Try both URLs first; an earlier copy may already be serving the app.
2. Identify the listeners using this read-only command:

```powershell
Get-NetTCPConnection -LocalPort 8010,3010 -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalAddress,LocalPort,OwningProcess
```

3. Look up a reported PID with `Get-Process -Id 1234` (replace 1234 with the actual PID). Stop the journal through its own server terminal with Ctrl+C when possible. Do not kill every Python/Node process.
4. Restart one backend and one frontend. Keep backend port 8010 because ChatGPT OAuth expects it. If frontend uses an offered alternative port, open the URL printed in its terminal; the sign-in callback's return link still points to 3010.

## Browser opens but data is missing or requests fail

1. Select **All Accounts**, clear Trade View's ticker/type/date filters and check the intended report period. Day Review has its own selected date.
2. Confirm backend health. In browser Developer Tools (**F12 → Network**), reload and inspect the failing request's status and response; do not share authorization headers or private response bodies.
3. For `ERR_CONNECTION_REFUSED` / Axios “Network Error,” confirm the frontend is requesting the expected localhost:8010 endpoint. A stale `REACT_APP_API_URL` can point elsewhere. Restart frontend after correcting it.
4. If requests succeed but the journal looks like a new install, stop the backend and check its launch directory and `DATABASE_PATH`. Running from a different directory can open/create a different database. A suddenly empty journal does not prove the original data was deleted.
5. Locate only the likely database files without printing their contents:

```powershell
Set-Location -LiteralPath 'C:\Projects\libre-trading-journal'
Get-Item -LiteralPath '.\trading_journal.db','.\backend\trading_journal.db' -ErrorAction SilentlyContinue |
    Select-Object FullName,Length,LastWriteTime
```

6. Use the intended database with the correct backend directory/configuration. If files need to be moved or restored, first follow [backup/restore](DATA-GUIDE.md#restore-without-losing-the-current-state); keep both candidates until you identify the right one.

For `403` on AI/MT5 routes, open the journal on **this computer's localhost**. These features deliberately reject remote origins and direct mutation requests without the journal header. Adding CORS origins does not disable this protection.

## Database errors

| Error | Safe response |
|---|---|
| `database is locked` | Stop duplicate app backends and close any DB editor holding a transaction. Reopen one backend. Do not delete WAL/SHM files. If OneDrive is synchronizing/conflicting, preserve files and investigate before relocating data. |
| `unable to open database file` | Verify `DATABASE_PATH`, parent directory existence, write permissions and OneDrive file availability. Prefer normal backend working directory. |
| `no such table/column` | Confirm correct database and current code. Startup initializes/migrates schema; inspect startup errors, back up, and have a developer examine the schema. Do not hand-delete tables. |
| `Unrecognized trades schema; asset migration was not applied.` | Migration intentionally stopped for an unexpected schema. Preserve database/backup and ask a developer to inspect it. Do not force-replace the schema. |
| `database disk image is malformed` | Stop the app, preserve database plus sidecars, and use a known good verified backup or specialist recovery. Do not repeatedly write/import into the damaged copy. |
| File access denied / OneDrive conflict | Ensure files are locally available and no other app is holding them. Preserve conflicting versions; do not accept a cloud conflict resolution blindly. |

The automatic `.before-multi-asset.bak` file is an old migration snapshot, not necessarily your latest journal. Verify dates/content before selecting it for restore.

## Import errors and unexpected results

| Message / symptom | What to do |
|---|---|
| `Please select a file and an account.` | Choose a specific account in the Import form and a CSV. Header All Accounts is not an import destination. |
| `Only .csv files are accepted` | Export/save CSV. Renaming an XLSX/HTML extension does not convert its contents. |
| Account not found | Refresh the app's account list and select the intended account. Verify the backend database if the account unexpectedly disappeared. |
| Unsupported headers / cannot detect broker | Pick the correct broker explicitly, or map the data into the matching supplied template. |
| Reported line/field error | Fix that line in a copy. Preserve ISO dates, decimals, positive quantities and required columns. Retry after all reported errors are addressed. |
| Exness commission must be negative/zero | Use signed broker commission in the position template. Do not reuse generic positive fee conventions. |
| Missing currency conversion | Supply the required account or quote USD rate; do not guess a current rate for historical money. |
| Duplicate ticket / partial-close conflict | Provide one fully closed position per ticket. Separate MT5 deals/partial closes need preprocessing; they are not accepted as independent rows with the same ticket. |
| “Imported 0” with skipped duplicates | Often expected for a repeated file in the same account. Check Trade View before importing elsewhere. |
| Import Complete also shows DB error(s) | Some trades may have saved. Inspect the request's `errors` list locally and compare counts before retrying. Do not assume all-or-nothing success. |
| Wrong P&L by 100/1,000/100,000 | Check lots versus units, multiplier/contract size, instrument type, currency conversion and cent-account units. Reconcile a single row first. |
| Corrected Exness price cannot be saved in execution editor | Correct the source CSV and reimport that ticket to preserve authoritative broker profit. |

Import result counts are trade groups, while skipped items can be described as duplicate executions; Exness operates on positions. Do not compare these counts directly to the number of CSV lines without understanding the format.

## AI provider errors

Open **More → Settings → AI connection**. Confirm the selected provider/model: every AI feature uses this selection. API options require that service's own key; put an OpenRouter Claude key under OpenRouter rather than direct Claude. Saving config does not verify access; **Test connection** makes a small request and can incur usage charges.

| Symptom | Recovery |
|---|---|
| Setup needed / Brain send disabled | Configure the selected provider, or deliberately switch to your connected ChatGPT option. |
| API authentication failed | Confirm key provider and validity. Replace it in Settings; never paste it into chat or a public issue. |
| Model unavailable / image unsupported | Refresh models or enter the exact provider ID. Screenshots require image support; typed notes work with text models. |
| API quota / credits exhausted | Check the selected API account's quota/billing. A ChatGPT/Claude subscription does not fund a separate API key. |
| Timeout / provider unavailable | Check network/provider status and retry deliberately. The app will not switch services automatically. |

See [provider setup and storage](AI-PROVIDERS.md) for the complete guide.

## ChatGPT coaching and diary errors

In Settings select **ChatGPT sign-in**, then use the **AI coach · ChatGPT** panel. A working journal does not require this connection.

| App message / symptom | Recovery |
|---|---|
| Connect ChatGPT in Settings / `not_connected` | Continue with ChatGPT, finish browser sign-in, then test. |
| Plan usage disabled / permission needed | Reconnect and review/enable plan usage if you intend to use it. Signing in without the required permission is insufficient. |
| Signed in but unverified | Select an available model and run **Test connection**. Only a completed response verifies inference. |
| Sign-in expired / invalid state / unverified callback | Start a fresh sign-in from Settings and complete it in the same browser. Keep backend 8010 running. Avoid replaying an old callback URL; OAuth attempts expire. |
| Session expired / authentication failed | Reconnect from Settings. |
| No models / invalid model | **Refresh models** and choose one currently available to that account. Model access is external and may change. |
| Usage/rate limit or entitlement error | Read the message and use **Manage ChatGPT usage**. Wait for applicable limits or resolve account eligibility. Do not repeatedly retry or enable paid credits merely to clear an error. |
| Timeout / interrupted stream / incomplete response | Check network, retry once with a smaller focused request, or try an available model. Repeated failure needs the error code and request ID, not token contents. |
| Credentials could not be opened | Try reconnecting. If every Settings operation also fails reading the damaged store, use the recovery step below. |
| Diary saved, but AI analysis failed | Inspect Diary: the file and record already exist. Fix the connection first. Reupload only deliberately; there is no retry-analysis button and reupload creates another record. |
| Could not convert this HEIC photo | Reinstall current backend requirements with the app's Python environment, then restart. Pillow and `pillow_heif` are included. If the image still fails, export JPEG/PNG and upload it. |
| Brain conversation vanished after reload | Expected current behavior: chat messages are browser-memory only. Copy important answers before reloading. |

**Damaged local ChatGPT store recovery:** stop the backend. In File Explorer, open `%LOCALAPPDATA%\TradingJournalAI\chatgpt`. Rename `connection.bin` to a dated recovery name, keeping it private rather than deleting it. Restart the backend and sign in again. This resets the local connection metadata and requires a new authorization; it does not change journal trades. If needed, revoke the old authorization in your ChatGPT account settings. Never paste the old file or callback query into a bug report.

## Backup and restore errors

| Symptom | Recovery |
|---|---|
| Invalid ZIP, checksum or schema | Keep the file and choose a complete backup made by this version. Arbitrary ZIPs/plain .db files cannot be restored through Settings. |
| Missing attachments | Preview identifies missing files. Restore is blocked; recover those files and create a complete backup. An incomplete current journal also prevents a safe pre-restore recovery copy. |
| Unsupported upload/settings/table | The app refuses silent data loss or credential leakage. Preserve data and ask the maintainer to inspect the compatibility issue. |
| File too large | Limits are 512 MiB ZIP, 1 GiB expanded, 256 MiB per file, 10,000 entries. Use advanced offline backup for larger journals. |
| Disk/permission failure | Preserve the automatic recovery copy. Fix space/permissions before retrying; inspect the current journal after rollback. |
| Restore and rollback failed / recovery-required 503 | Keep the indicated ZIP and upload recovery folder. Normal requests are blocked in this server process. Recover offline before restarting; recovery downloads remain available. |
| Restored but old accounts/forms still visible | Click **Reload journal** and reload other open tabs. Restore replaces every account. |
| AI/MT5 disconnected after moving machine | Expected: backups exclude credentials. Reconnect services on the destination. |

Follow [backup/restore and recovery](BACKUP-RESTORE.md). Use **Saved recovery copies** to download the previous journal even after reloading Settings. Do not test a restore against the real journal merely to investigate a bug.

## MT5 and other chart errors

| Message / symptom | Recovery |
|---|---|
| Connect this journal account to MT5 | Set up **More → Settings → Market data · MT5** for the same journal account as the trade. |
| Cannot reach MT5 MCP | Keep MT5 open, enable its internal MCP server if available, and verify the exact localhost `/mcp` address. If MCP is absent from the terminal, use the Python method. |
| MCP rejected access key/permission | Re-enter the current key from MT5 locally. Do not put it in `.env`, chat or a screenshot. |
| Saved MCP key could not be opened | Reconnect in Settings and provide the key again; Windows-user/machine changes can invalidate its encrypted storage. |
| MT5 support is not installed | Use the repo's Windows Python environment; reinstall backend requirements and restart. |
| Select `terminal64.exe` / cannot initialize | Select the actual installed terminal executable, open it and sign in there first. |
| Different account / provider does not match | Restore the saved account in MT5 or intentionally reconnect the journal to the new account/provider. Do not bypass the identity check. |
| Symbol unavailable / several symbols match | Use the exact Market Watch symbol including suffix. Confirm the provider carries that instrument. |
| No candles/history | Open the symbol and timeframe in MT5, wait for history to load, check trading dates/hours and Max. bars in chart, then retry. |
| Execution markers shifted by hours/date | Check trade clock separately from MCP server clock for the historical date. Exness imports use UTC+0; do not automatically select UTC+8 because the computer is in Manila. |
| Price differs from broker execution | Check provider, symbol and reference-price label. Another broker's candles, spreads and execution prices can differ. |
| Alpaca key warning | Configure optional Alpaca keys in `backend/.env` and restart backend; MT5/TradingView login does not supply those keys. |
| Alpaca feed error | Set `ALPACA_DATA_FEED=iex` or omit it; a blank assignment is not the code default. Paid `sip` requires appropriate access. Check key validity without posting it. |
| Futures chart looks like an ETF | The current stock provider maps some futures to proxy ETFs. It is not an exact futures price feed. |

## What to give the next AI or developer

Copy this small report and fill it in; redact account names/numbers and financial details if sharing externally:

```text
Page/action:
Expected result:
Actual result and exact error:
When it started / what changed:
Backend http://127.0.0.1:8010/ returns:
Frontend URL being used:
Backend/frontend startup directory:
First relevant terminal error (redacted):
Browser failed request: path + status + redacted error/code/request ID:
Python / Node versions:
Last known good backup date:
Steps already tried:
```

For code work, also provide `git status --short` and `git log -1 --oneline` from the **app repository**. Do not provide `.env`, auth headers, OAuth callback URLs, access keys, full real statements or database contents. Ask the next AI to read [AGENTS.md](../AGENTS.md) and [PROJECT-STATUS.md](PROJECT-STATUS.md) before changing anything.
