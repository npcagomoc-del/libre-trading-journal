# Data, calculations, backup and restore

This document describes inspected local code as of **2026-10-04**. It does not certify that a particular broker statement or live account has been reconciled.

## What lives where

Under normal `launch.bat` startup:

| Location | Contents / handling |
|---|---|
| `backend/trading_journal.db` | SQLite journal: accounts, trades, diary records/analysis, settings and library. |
| `backend/trading_journal.db-wal`, `-shm` | SQLite write-ahead-log sidecars when active. Do not delete them to clear an error. |
| `backend/uploads/` | Uploaded diary images/text, linked by filename in diary records. Back up with the database. |
| `backend/.env` | Optional credentials/configuration; private, not version-controlled. |
| `*.before-multi-asset.bak` beside database | First pre-migration snapshot if the old asset constraint is migrated. It is not a continuing backup schedule. |
| `%LOCALAPPDATA%\TradingJournalAI\chatgpt\` | ChatGPT connection store/lock. Windows DPAPI-protected `connection.bin`; outside this OneDrive checkout. |
| `%LOCALAPPDATA%\TradingJournalAI\ai-providers\` | DPAPI-protected API keys, model configuration and active AI provider; separate from journal backups. |
| `%LOCALAPPDATA%\TradingJournalAI\backups\` | Automatic pre-restore recovery ZIPs. Private journal data; download from Settings or preserve locally. |
| `%LOCALAPPDATA%\TradingJournalAI\mt5-mcp\` | Windows-encrypted MCP credentials; database stores an opaque reference plus non-secret feed config. |
| Original broker CSVs wherever you saved them | The CSV import endpoint parses bytes and stores normalized executions; it does **not** archive the original uploaded broker CSV. Keep originals separately. |

`DATABASE_PATH` and `UPLOAD_DIR` can override the first three locations; relative values resolve against backend working directory. Inspect only those configuration names locally if you need to locate data. Do not publish `.env` to obtain support. The root-level `uploads/` folder is not necessarily the active upload store; it can result from importing/running code with a different working directory.

Core journal use is local, but this workspace is inside **OneDrive**, so filesystem synchronization may copy files according to your OneDrive settings. App “local” storage is not a promise that your operating system/cloud sync never copies it. An active SQLite database should not be treated as a multi-computer shared database. Use consistent backups for transfer.

## Database map

| Table | Important fields and meaning |
|---|---|
| `accounts` | Local ID, name, account type, color and broker label. |
| `trades` | Account ID, unique `(trade_group, account_id)`, report date, ticker, instrument, Long/Short, gross/net P&L, commissions, swaps, executions JSON, import/source metadata; setup and optional excursion metrics. |
| `trade_analysis` | Unique trade group; strategy, stop, target, risk/R fields, reasons, mistakes, emotion, notes, rating, idea source, feedback, match confidence and optional diary link. |
| `trade_tags` | Trade group, tag type/value and AI/manual source. |
| `diary_entries` | Account, date, uploaded filename, raw text field, analysis JSON and created timestamp. Current upload flow saves original content as a file rather than filling `raw_text`. |
| `daily_summaries` | Cached content/date/account and generation time; daily and weekly routes use this storage. |
| `settings` | Account/key/value pairs; goals and MT5 configuration are examples. |
| `custom_setups` | Named playbook setups. |
| `library_items`, `library_aliases` | Strategy/source/tag names, descriptions and remembered merge aliases. |

Execution JSON contains date, time, `BOT`/`SOLD`, quantity, price, commission and instrument/sizing fields where applicable. Exness executions additionally preserve broker ticket/profit/currency/clock metadata. Treat JSON as part of the data model when migrating; a table-column-only export loses essential information.

Brain messages exist in frontend React state, not a persisted chat table. Page reload loses that conversation. Diary analysis and stored review content survive in SQLite. Deleting a diary row leaves trade analysis intact and does not remove its uploaded file; deleting a trade removes its linked analysis/tags in the trade endpoint. There is no general undo/recycle bin.

## Generic execution format

Use the [blank template](../frontend/public/templates/generic_trades_template.csv) or [worked example](../frontend/public/templates/generic_trades_example.csv).

| Column | Meaning |
|---|---|
| `date`, `time` | Required fill date/time. Prefer ISO `YYYY-MM-DD` and 24-hour time. Supported US month-first dates are distinct from refused ambiguous day-first input. |
| `symbol`, `side` | Required ticker and buy/sell action; recognized aliases include BUY/SELL, BOT/SOLD and short/cover labels. |
| `quantity`, `price` | Required positive quantity and fill price; fractional quantity supported. |
| `commission` | Optional USD cost for this fill; zero if blank. |
| `asset_type` | STOCK default, OPTION, FUTURE, CRYPTO, FOREX or GOLD. |
| `expiry`, `strike`, `put_call` | Option identity fields; options use 100 multiplier. |
| `multiplier` | Contract size/point value. Default 1 for crypto/forex/gold units; known futures have point values. Supply the correct value for lots/contracts. |
| `quote_currency` | Price quote currency, USD default. |
| `quote_to_usd_rate` | Required for non-USD quotes: USD per one quote-currency unit. Commissions remain USD. |

Fills group into position open/close cycles rather than simply one trade per ticker per day. Duplicate detection is account-scoped and supports overlapping imports. Closed grouped trades use closing-fill date; open positions use their latest fill date. Non-USD generic grouping uses the final fill's supplied conversion rate; contract size and quote currency must remain consistent within a position.

Parser errors stop the import before database writes. Later database-write errors are collected per trade and successful rows can still commit, so inspect the import response before claiming the whole file was atomic.

## Exness position format

Use the [position template](../frontend/public/templates/exness_positions_template.csv) or [example](../frontend/public/templates/exness_positions_example.csv). Each row is one fully closed ticket, not one execution.

| Field | Meaning |
|---|---|
| `ticket`, `symbol`, `side`, `lots` | Position identity, exact broker symbol, buy/sell and positive fractional lots. |
| `open_time`, `close_time` | Original broker timestamps; use ISO or MT5 `YYYY.MM.DD HH:MM:SS`. Close time cannot precede open time. |
| `open_price`, `close_price`, `profit` | Both prices and authoritative broker gross profit. |
| `commission`, `swap` | Signed commission (negative/zero); swap keeps its sign. Optional separate `fee` is a nonnegative cost. |
| `stop_loss`, `take_profit` | Optional broker planning levels. |
| `contract_size` | Optional override; default 100 for XAUUSD, 100,000 for forex. Confirm broker specifications. |
| `account_currency`, `account_to_usd_rate` | Money currency/default USD and conversion to USD. Standard units only; pre-convert cent-account amounts. |
| `quote_to_usd_rate` | Optional price quote conversion metadata; distinct from account-money conversion. |

Comma CSVs use dot decimals and may quote thousands separators. Semicolon/tab formats also accept decimal commas. Symbol suffixes are retained. Conflicting duplicate ticket rows, including partial-close rows sharing a ticket, are refused. Position IDs use `exness_<journal-account-id>_<ticket>`, keeping overlapping tickets in different accounts separate.

Identical reimports skip. Corrected tickets update stored broker values and executions while retaining notes/tags; broker stop/target updates preserve independently edited values according to the existing-value check in `main.py`. Reports use the closing date. Exness metadata specifies UTC+0 for chart placement; the parser preserves timestamps without changing their clock.

## Money calculations

- Manual closed long: `(exit - entry) × quantity × multiplier × quote-to-USD rate`.
- Manual closed short: `(entry - exit) × quantity × multiplier × quote-to-USD rate`.
- Manual/generic net: gross minus USD commissions. Grouped fills account for each execution and its side.
- Exness gross: broker `profit × account_to_usd_rate`, rounded to cents. The app does not replace broker profit with an entry/exit calculation.
- Exness stored commission cost: `(-signed commission + separate fee) × account_to_usd_rate`, rounded to cents.
- Exness stored swap: signed swap times that rate, rounded to cents.
- Exness net: rounded gross minus rounded commission cost plus rounded swap. Decimal half-up rounds the monetary components before computing net.

Thus profit `20`, signed commission `-0.70`, swap `-0.10`, no separate fee, USD account → gross `$20.00`, stored commission `$0.70`, swap `-$0.10`, net `$19.20`.

This is a USD journal. A quote currency or non-USD broker account does not change dashboard totals to that currency. No live exchange rate is guessed. Quantity `0.1` lots with multiplier `100000` means 10,000 base units; using multiplier 1 would be a different position size.

An open manual trade stores gross 0 and net minus commissions; it is not marked to current market prices. Editing generic/manual executions can recalculate results. Exness edit restrictions preserve broker-profit authority; correct its price/lot records through reimport.

## Metrics and interpretation

The following describe `/api/kpis` in `backend/main.py`; some report buckets use different formulas. They are documented behavior, not a claim that all definitions are ideal.

| Metric | Current calculation / caveat |
|---|---|
| Net/gross P&L | Sum stored values for selected account/date range. |
| Trade win rate | Positive-net trades divided by **all selected trades**; zero-net trades remain in denominator. Open records are not excluded by this query. |
| Average win/loss | Mean positive/negative net P&L; average loss is negative. |
| Expectancy | Winner proportion × rounded average win + loser proportion × rounded average loss. |
| Profit factor | Gross P&L summed for net-positive winners divided by absolute gross P&L summed for net-negative losers; null if loss denominator is zero. This can diverge from a net-profit-factor definition when fees turn a gross winner into a net loser. |
| Day win rate | Positive-net recorded days divided by recorded trading days. |
| Equity curve | Cumulative selected-period daily net P&L from zero; excludes deposits/withdrawals and starting capital. |
| Max drawdown | Most negative cumulative P&L minus running peak, using daily totals and an initial peak of zero. Does not capture every intraday dip. |
| Strategy breakdown | Playbook setup first, diary strategy fallback. Current `/api/kpis` strategy subquery applies account but not requested date limits and excludes zero-net rows. Treat a mismatch with the selected period as a known limitation. |
| MFE / MAE / exit efficiency | Optional stored chart-derived excursions/efficiency. Missing values mean unavailable/uncomputed, not zero. Candle/provider accuracy and hold-window coverage matter. |
| Realized R / risk / grades | Analysis fields can come from user or AI. Inspect provenance and stop/risk assumptions; these are not uniformly recalculated from executions. |

When reconciling, start with one account and a known small date range; compare individual trades to the statement before comparing headline metrics. The [status guide](PROJECT-STATUS.md) lists proposed follow-up fixes for these differences.

## Backup a consistent journal

Back up before updates, migrations, bulk imports/edits and restore attempts. Normally use **More → Settings → Backup & restore → Download backup**, then **Check backup** to inspect counts and attachments. The [built-in backup tutorial](BACKUP-RESTORE.md) explains the current-format ZIP, credentials excluded, all-account replacement and automatic recovery. There is no scheduled backup.

The following is an **advanced offline folder backup**, distinct from the built-in ZIP format. Stop both app servers first so diary files and database stay at one point in time. It uses SQLite's backup API, including committed WAL data, and optionally copies private .env configuration. Do not upload this folder as a built-in restore ZIP.

From **app root**, after stopping the app, with the default paths (edit the two source paths if configured differently):

```powershell
$journalDb = Join-Path (Get-Location) 'backend\trading_journal.db'
$journalUploads = Join-Path (Get-Location) 'backend\uploads'
if (-not (Test-Path -LiteralPath $journalDb)) { throw 'Journal database not found; verify DATABASE_PATH before continuing.' }
$journalBackup = Join-Path $env:LOCALAPPDATA ('TradingJournalAI\backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $journalBackup -ErrorAction Stop | Out-Null
@'
import pathlib, sqlite3, sys
source = pathlib.Path(sys.argv[1]).resolve()
target = pathlib.Path(sys.argv[2]) / 'trading_journal.db'
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
        result = dst.execute('PRAGMA integrity_check').fetchone()[0]
        if result != 'ok':
            raise RuntimeError(result)
print('Database backup integrity: ok')
'@ | .\.venv\Scripts\python.exe - $journalDb $journalBackup
if ($LASTEXITCODE -ne 0) { throw 'Database backup failed; do not use this backup for restore.' }
if (Test-Path -LiteralPath $journalUploads) {
    Copy-Item -LiteralPath $journalUploads -Destination (Join-Path $journalBackup 'uploads') -Recurse -ErrorAction Stop
}
if (Test-Path -LiteralPath 'backend\.env') {
    Copy-Item -LiteralPath 'backend\.env' -Destination (Join-Path $journalBackup 'backend.env') -ErrorAction Stop
}
Write-Output "Backup folder: $journalBackup"
```

Treat the backup as private: it can contain financial records and API keys. Copy it to another protected destination/device for disaster recovery; a local backup on the same disk does not protect against disk loss. Record any custom database/upload path and app version alongside it. Keep your original broker files separately.

The connection stores are intentionally not copied by this procedure. Reconnect ChatGPT, API providers and MT5 after moving machine/user. Windows DPAPI data is user-bound and is not a portable login backup. On non-Windows, ChatGPT/API stores are permissions-restricted files without DPAPI; MT5 MCP encrypted credentials require Windows.

## Restore without losing the current state

For a valid built-in ZIP and a healthy app, use [Settings restore](BACKUP-RESTORE.md#restore-a-backup). The steps below are **manual offline recovery** for an advanced folder snapshot. If recovering from a built-in ZIP, extract a trusted copy into a new staging folder: its database is named `journal.sqlite3`, not `trading_journal.db`, and it contains `uploads/` and `manifest.json`. Inspect that database read-only before copying it to the actual configured database path. Built-in ZIPs contain no .env. Keep the original ZIP and any failed-restore recovery files untouched until recovery is verified.

1. **Stop the frontend and backend.** Verify no journal backend process is still serving port 8010. Do not restore over a running database.
2. Make a fresh backup of the current journal using the procedure above. Keep it even if the current state appears wrong.
3. Select the intended backup by its full path. Check its database before use with the read-only command below. Do not restore an empty newly created database accidentally.
4. In File Explorer, create a dated recovery folder. Move the current active database and any matching `-wal`/`-shm` sidecars into it **together**, after the app is stopped. Move the active uploads folder there too if restoring a matching complete snapshot. Keep this recovery folder; do not delete it.
5. Copy the backup's `trading_journal.db` into the configured active database path. Copy its `uploads` folder to the configured upload path. Do not leave old WAL/SHM files beside the restored database and do not combine attachments from an unrelated snapshot blindly.
6. Restore `backend.env` as `backend/.env` only if those settings/keys are still intended; otherwise keep current configuration. A path inside that file may refer to the old machine.
7. Start the app and check accounts, trade counts, a known date's totals and several diary attachments. Reconnect services if needed. Keep all recovery copies until satisfied.

Read-only integrity check from app root; replace the example path with the actual backup:

```powershell
$journalRestoreCandidate = 'C:\full\path\to\backup\trading_journal.db'
@'
import pathlib, sqlite3, sys
path = pathlib.Path(sys.argv[1]).resolve()
with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
    print(db.execute('PRAGMA integrity_check').fetchone()[0])
'@ | .\.venv\Scripts\python.exe - $journalRestoreCandidate
```

Expected output is `ok`; anything else needs investigation before restore. The placeholder is deliberate because only you know which backup to restore. SQLite integrity is structural validation, not proof of financial correctness or complete attachments. Restore tests and browser checks use synthetic disposable journals; the user's real journal was not restored.

## Source references

The main references are [database.py](../backend/database.py), [main.py](../backend/main.py), [csv_parser.py](../backend/csv_parser.py), [exness_parser.py](../backend/exness_parser.py), [instruments.py](../backend/instruments.py), [library.py](../backend/library.py), [chatgpt_provider.py](../backend/chatgpt_provider.py) and [mt5_mcp.py](../backend/mt5_mcp.py). Check those implementations when changing a data rule.
