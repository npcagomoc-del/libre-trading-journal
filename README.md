# Libre Trading Journal

Libre Trading Journal is based on [Trading-Journal-AI](https://github.com/simonro/Trading-Journal-AI) by **Simon (simonro / Tape to Edge)**. Libre adds multi-provider AI, additional broker/asset integrations, and journal backup/restore. The original [MIT license and copyright](LICENSE) are retained. This is an early source preview for local, single-user use.

**Download on your PC:** [Download source ZIP](https://github.com/npcagomoc-del/libre-trading-journal/archive/refs/heads/main.zip), extract it, then follow the [Windows installation tutorial](docs/INSTALL-WINDOWS.md). Install Python 3.11+ and Node.js 24 with npm, run `setup.bat` once, then `launch.bat`. Open http://localhost:3010 on the PC running the app.

Choose **More → Settings → AI provider** for ChatGPT sign-in, an OpenAI API key, a Claude API key, or an OpenRouter API key. Brain, diary analysis, insights, and reviews use the selected provider. API usage is billed by the provider; the core journal works without AI. See the [AI provider guide](docs/AI-PROVIDERS.md).

Use **More → Settings → Backup & restore** to download a journal ZIP, check a backup, or restore it with a recovery copy created first. Backups include the database and diary attachments, excluding API keys, OAuth tokens, and .env files. See the [backup guide](docs/BACKUP-RESTORE.md).

## Start here

The upstream overview and screenshots below remain useful, but may differ from the current Libre branding and features. See the dated [project status](docs/PROJECT-STATUS.md) for actual implementation and verification.

| I want to… | Guide |
|---|---|
| Download and install on a new Windows PC | [Windows installation](docs/INSTALL-WINDOWS.md) |
| Open the app and learn the daily workflow | [User guide](docs/USER-GUIDE.md) |
| Fix startup, import, AI or chart errors | [Troubleshooting and recovery](docs/TROUBLESHOOTING.md) |
| Know what is completed, unverified or unfinished | [Project status](docs/PROJECT-STATUS.md) |
| Set up, understand or maintain the code | [Developer guide](docs/DEVELOPER-GUIDE.md) |
| Understand data, calculations or backup/restore | [Data guide](docs/DATA-GUIDE.md) |
| Understand design choices and evidenced changes | [Decisions](docs/DECISIONS.md) · [Changelog](docs/CHANGELOG.md) |
| Ask a future AI to continue safely | [AI instructions and reading order](AGENTS.md) |

For ordinary use, run `launch.bat` **from this app folder**, keep both server windows open, and open [http://localhost:3010](http://localhost:3010). First-time setup is below. If startup fails, begin with the troubleshooting guide; do not delete the database. Review local changes and back up before updating.

### Exness / MT5 Forex & Gold imports

Choose **Exness / MT5 (Forex & Gold)** on Import and download its template/example. Use one row per fully closed ticket, including opening/closing prices and timestamps, broker profit, signed commission and swap. Native MT5 HTML reports, individual deal/order rows and partial closes sharing a ticket are unsupported.

Follow the [Exness import tutorial](docs/USER-GUIDE.md#3-import-exness--mt5-forex-and-gold-history) for the workflow and [position-format reference](docs/DATA-GUIDE.md#exness-position-format) for sizing, currencies and repeat/corrected imports. The generic template uses one row per fill instead.

The walkthrough and screenshots below are from the **upstream project**. Libre's CI checks are linked here; a passing build does not establish live AI-provider access.

[![CI](https://github.com/npcagomoc-del/libre-trading-journal/actions/workflows/ci.yml/badge.svg)](https://github.com/npcagomoc-del/libre-trading-journal/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A trading journal that runs on your own machine. Import your broker's CSV and it rebuilds your
round-trip trades, tracks the numbers that matter (win rate, profit factor, expectancy, drawdown,
MFE/MAE, exit efficiency), and, if you want it to, uses your selected AI provider to read your trading diary and grade
your days on process.

- **Your journal is stored on your computer.** One SQLite file, no telemetry. Optional coaching sends relevant context to the selected AI service.
- **The numbers are not AI.** Trade grouping, P&L, fees and statistics are plain code with tests.
  AI is an optional coaching layer on top.
- **Stocks, options, futures, crypto, forex and gold**, with partial fills, scale-ins and shorts grouped automatically.
- **Thinkorswim, Interactive Brokers and Exness** importers, plus a generic fill template for other broker exports.
- **Free and MIT licensed.** No paid tier.

**[Quick start](#quick-start)** · **[Original creator's walkthrough](https://www.youtube.com/watch?v=LTR4HOfS_hc)** · **[Libre source](https://github.com/npcagomoc-del/libre-trading-journal)** · **[Privacy](#privacy-and-your-data)**

**What this is not:** Not financial advice. Not a signal service. Every screenshot below is the
synthetic demo seed, not anyone's real trades.

![The dashboard: net P&L over a live equity curve, every session as one strip, measures against your goals, and the month beside your recent trades](docs/screenshot-dashboard.png)

## Privacy and your data

Libre Trading Journal is designed as a **local-first application**.

Your trading journal database, imported broker data, notes, and uploaded files are stored locally on your computer. Libre Trading Journal does not require a service login for core journaling and does not include telemetry or analytics that send your usage data back to the project. The backend listens on `localhost` only. If you place the app in OneDrive or another synced folder, your operating system's sync settings can copy local journal files; see the data guide before treating it as a shared database.

### What stays local

- Your trading database
- Normalized imported broker records (keep your original CSV exports separately; the importer does not archive the original file)
- Trade history and performance data
- Journal entries and notes
- Uploaded diary files and images
- Application settings

### Optional external services

Some features use third-party APIs and are completely optional.

**Optional AI providers (this local version)**

When you use AI analysis or Brain, the information required to answer your request is sent to the provider selected in Settings: OpenAI through ChatGPT sign-in or an API key, Anthropic, or OpenRouter and its model provider. This can include trade information, journal context, and supported diary images. Switching providers is explicit; failures do not trigger an automatic provider switch.

The core journal, trade reconstruction, P&L calculations, reports, and statistics do not require ChatGPT.

**Market data (Alpaca)**

If you add Alpaca keys, the trade chart asks Alpaca for price bars: the ticker and the date range,
nothing about your trades or account.

### API keys

API keys are configured locally and should never be committed to GitHub.

Do not share or commit:

- `.env` files
- API keys or secrets
- Local database files
- Raw broker statements containing personal information
- Screenshots containing account numbers or other sensitive financial information

The repository's `.gitignore` is configured to exclude common local data and credential files.

### Deterministic calculations

AI is not used to calculate your trading results.

Trade reconstruction, P&L, commissions, statistics, and other core trading calculations are handled by deterministic application code. AI features are an optional analysis and coaching layer on top of those calculations.

## What's inside

- **Dashboard**: your net P&L over a live equity curve (hover it for any day's running balance),
  every session in the period as a single strip you can scrub, measures against your own goals,
  the month beside your recent trades and open positions, and a tabbed breakdown by time of day,
  day of week and strategy
- **Trade View**: every trade with executions, playbook setup tags, MFE/MAE and exit efficiency, its AI analysis and an intraday chart with your fills on it
- **Reports**: breakdowns by day of week, time of day, hold time, setup, grade, symbol, side, emotion,
  plus a Sources & Tags tab that scores where your ideas come from. One switch flips the whole page
  between bars and full numeric tables, and rows under ten trades are marked thin so a one-trade
  strategy at 100% cannot sit at the top
- **Diary**: upload handwritten notes, screenshots, or typed text; the selected AI model extracts strategy, stops, R-multiples, emotional state, and mistakes, and matches them to your actual trades
- **Day Review**: the session drawn as one picture, running P&L from the open to the close with every
  trade marked where you entered it, plus an AI coaching report graded on process rather than P&L.
  Each trade's grade carries the reason it was given
- **Brain**: a chat that answers questions against your full trading history
- **Settings**: AI provider selection, journal backup/restore, MT5 market data, and the name library. Strategies, sources and tags in one place, with rename, merge and
  delete. Merging rewrites every trade that used the old name and remembers it, so the next diary
  analysis that produces the duplicate saves it under the name you kept
- **Import**: Thinkorswim account statement CSV and Interactive Brokers (IBKR) Activity Statement CSV, with a broker dropdown (auto-detect by default). Any other broker imports through a generic CSV template, one row per fill

## Screenshots

**Trade View.** Every trade with its executions, MFE/MAE and exit efficiency, the realized R, and the
setup you tagged. Click any row to open the full trade.

![Trade View: the trade log with setups, excursion and R columns](docs/screenshot-trade-view.png)

**Trade Details.** The executions on one trade, the planned and realized R, the stop and target you
wrote before entry, and an intraday chart with your fills marked on it. Charts open on the trade
day's session; the legend entries switch layers on and off.

![Trade Details: executions, R-multiple, stop and target, and an intraday chart with fills](docs/screenshot-trade-detail.png)

**Day Review.** The session as one picture: running P&L from the open to the close with every trade
marked where you entered it. The day's measures sit under it, each set against your all-time figure:
win rate, profit factor, average win, average per trade against your expectancy, exit efficiency,
and how much was given back from the session high. Underneath, an AI coaching report graded on process rather than P&L,
which reads your trades and your diary together and is willing to tell you a profitable day was
badly run.

![Day Review: the session drawn as running P&L with each trade marked, day measures, and an AI coaching report](docs/screenshot-day-review.png)

**Reports.** Equity curve, drawdown against the running peak, and breakdowns by setup, timing,
execution, symbol, source, tag and psychology.

![Reports: equity curve, drawdown from peak, and monthly performance](docs/screenshot-reports.png)

**Settings.** The vocabulary the journal uses. Rename a strategy, merge two that mean the same thing,
or delete one and reassign its trades.

![Settings: the strategy, source and tag library with rename, merge and delete](docs/screenshot-settings.png)

## Watch the walkthrough

[![Watch: I built my own AI trading journal and stopped paying monthly](docs/video-thumbnail.png)](https://www.youtube.com/watch?v=LTR4HOfS_hc)

Simon's walkthrough covers the original app, installation and customization prompts. Libre's AI provider and backup controls are covered in the guides above.

## Quick start

Requirements: [Python 3.11+](https://www.python.org/downloads/) and [Node.js 24 with npm](https://nodejs.org/). Windows is the primary user installation path. Backend CI also runs on Linux; MT5 desktop integration requires Windows. See the [developer guide](docs/DEVELOPER-GUIDE.md) for exact commands and verification limits.

**Windows, two steps:** download or clone the repo, then double-click

1. `setup.bat`, once. It creates the Python environment, installs everything and creates
   `backend\.env` for your optional keys.
2. `launch.bat`, every time. Then open http://localhost:3010

For manual Windows setup, use the [PowerShell instructions](docs/DEVELOPER-GUIDE.md#setup-on-windows).

**Manual setup on macOS/Linux (advanced):** macOS has not been tested. These commands run the core journal and frontend; they do not provide Windows MT5 integration. From the extracted/cloned repository root:

```bash
# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

Then open two terminals in the repository root. Keep both running:

```bash
# Terminal 1: backend
source .venv/bin/activate
cd backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8010
```

```bash
# Terminal 2: frontend
cd frontend
PORT=3010 npm start
```

Open http://localhost:3010. Optional Alpaca configuration goes in `backend/.env`; create it from `.env.example` if needed. Keep the backend on 8010 and frontend on 3010 for ChatGPT sign-in.

To run them on other ports, tell each side about the other: `REACT_APP_API_URL` for the frontend,
and, only if the frontend is not on localhost, `FRONTEND_ORIGINS` (comma separated) for the
backend's CORS allow list. Any localhost port is accepted without configuration.

Every install starts empty: no accounts, no trades, no demo data. Add your first account in the app,
then import your broker's statement on the Import page.

## Updating to a new release

With normal launcher startup, your trades live in `backend/trading_journal.db`, diary attachments in
`backend/uploads/`, and optional settings/keys in `backend/.env`. Custom paths can override these.
Before updating, download and check a backup in **Settings → Backup & restore**, then stop both server windows. Startup can migrate existing tables, including a transactional rebuild for the multi-asset constraint. The migration backup is not a replacement for regular backups.

Follow the [developer update procedure](docs/DEVELOPER-GUIDE.md#extend-or-update-safely)
before updating or merging upstream changes. Do not blindly overwrite local data or code changes with a ZIP.
The examples below apply only after reviewing/preserving local work.

**If you cloned with git:**

Windows PowerShell, from the app root; run each command separately and stop at any error:

```powershell
git status --short
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Push-Location frontend
npm.cmd ci
Pop-Location
.\launch.bat
```

If `git status` lists changes or `git pull --ff-only` refuses, preserve the files and follow the developer update guide instead of forcing the update. On macOS/Linux, use the activated virtual environment and the manual startup above.

**If you downloaded the ZIP:** extract the new source into a separate folder, run setup and launch there, then use **Settings → Backup & restore** to check and restore your saved journal ZIP. Keep the old folder and backup until you verify your records and attachments. Reconnect AI and MT5 credentials on the new installation, and copy intended optional Alpaca configuration privately. Follow the [backup tutorial](docs/BACKUP-RESTORE.md).

If the app cannot start, the [advanced offline backup/recovery guide](docs/DATA-GUIDE.md#backup-a-consistent-journal) explains consistent SQLite snapshots and uploads. Do not copy an active database without its committed WAL data.

To check what changed, see the [changelog](docs/CHANGELOG.md) and [Libre commit history](https://github.com/npcagomoc-del/libre-trading-journal/commits/main/).

## Importing from a broker that is not listed

Thinkorswim and Interactive Brokers have dedicated importers. For anything else, use the generic
template: one row per fill, which the journal groups into round-trip trades exactly like a broker
import. On the Import page, open **Broker not listed?** to download it.

- Blank template: [`frontend/public/templates/generic_trades_template.csv`](frontend/public/templates/generic_trades_template.csv)
- Worked example: [`frontend/public/templates/generic_trades_example.csv`](frontend/public/templates/generic_trades_example.csv)
  (a long with a partial exit, a short, an option and a micro future)

| Column | Needed | What goes in it |
|---|---|---|
| `date` | Required | `YYYY-MM-DD`, or `MM/DD/YYYY`. Day-first dates are refused because `03/04` is ambiguous |
| `time` | Required | 24 hour `HH:MM` or `HH:MM:SS`, or `1:05 PM` |
| `symbol` | Required | `AAPL`. Futures start with a slash: `/MESU26` |
| `side` | Required | `BUY` or `SELL`. `BUY TO COVER`, `SELL SHORT`, `BOT` and `SOLD` work too |
| `quantity` | Required | Shares or contracts, always positive |
| `price` | Required | Fill price per share or per contract |
| `commission` | Optional | Fees for that fill. Blank means 0 |
| `asset_type` | Optional | `STOCK` (the default), `OPTION`, `FUTURE`, `CRYPTO`, `FOREX` or `GOLD` |
| `expiry`, `strike`, `put_call` | Options | `2026-08-28`, `765`, `CALL` or `PUT`. Options use a 100 multiplier |
| `multiplier` | Optional | Point value for a future the app does not know, for example `50` for `/ES` |

Columns can be in any order, common names such as `Ticker`, `Qty` and `Fees` are recognised, and
extra columns are ignored, so an export that already uses these headers imports without editing.

If any row cannot be read, **nothing is imported** and the error names the line and the problem. A
silently skipped fill would change every P&L figure after it, so the importer refuses instead.

Adding a dedicated parser for your broker is welcome: open an issue with a sample export that has
the account numbers and personal details removed, or send a pull request against
`backend/csv_parser.py`. Every parser only has to produce execution rows; grouping, duplicate
detection and P&L are shared.

## Environment variables

The AI coach uses the provider selected in **Settings → AI provider**. **ChatGPT sign-in** retains the existing plan OAuth flow: continue with ChatGPT, allow plan usage if offered, choose an available model, then test. The **OpenAI API key**, **Claude API key**, and **OpenRouter API key** choices instead use the user's own API account and model. An OpenRouter key belongs in OpenRouter, not in the direct Claude field. API use has separate billing. A saved key is configured, not verified, until a test response completes. Brain, diary, daily/weekly reviews, and insights all share this selection. See [setup and error recovery](docs/AI-PROVIDERS.md).

To prevent extra spending, leave **Allow apps to use credits after reaching your usage limit** disabled in [ChatGPT Usage settings](https://chatgpt.com/settings/usage). This app never falls back to API-key billing. If plan usage is unavailable or exhausted, coaching shows an error.

On Windows, tokens are encrypted for your Windows user with DPAPI and stored under `%LOCALAPPDATA%\TradingJournalAI\chatgpt`, outside the repository. Disconnect in Settings to remove local tokens and attempt remote revocation. You can also revoke the app in ChatGPT settings. The OAuth callback is `http://127.0.0.1:8010/auth/callback`; keep the backend on port 8010.

`backend/.env` is only needed for optional market data. Copy `.env.example` there if it is missing, fill in the Alpaca credentials, then restart the backend. TradingView and MT5 credentials do not replace Alpaca credentials in the existing chart provider.

| Variable | Enables |
|---|---|
| `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` | Intraday price charts on each trade |
| `ALPACA_DATA_FEED` | Defaults to `iex`. Set `sip` only with a matching paid market-data subscription. |
| `FRONTEND_ORIGINS` | Optional extra frontend origins for non-AI routes. AI coaching and sign-in require a local browser origin. |

Official integration reference: [Sign in with ChatGPT for open-source apps](https://developers.openai.com/siwc/token-sharing-open-source).

## Customize with an AI coding assistant

The original Trading-Journal-AI app was built by Simon with Claude Code, one session at a time. The Libre modifications build on that foundation. The upstream customization approach remains useful; the actual AI instructions for this repository are in [AGENTS.md](AGENTS.md).

You can use an AI coding assistant to adapt the app. Start it with [AGENTS.md](AGENTS.md) so it knows the code map, data safeguards and checks. A sample prompt:

**Adapt the importer to your broker:**

> Read AGENTS.md, docs/PROJECT-STATUS.md and backend/csv_parser.py. Using the synthetic broker sample below, add a fill-based importer following parse_ibkr_csv and the CONTRIBUTING guide. Register it in BROKER_PARSERS and BROKER_LABELS, update detect_broker and the Import dropdown/export instructions, and add regression tests with hand-worked expected P&L. Preserve account-scoped duplicate detection, notes/tags, asset multipliers and currency conventions. Use a disposable database and never read or modify the real journal. Update the affected guides and report the checks performed.

## Contributing

Bug reports, broker samples and pull requests are welcome. [CONTRIBUTING.md](CONTRIBUTING.md) covers
the setup, the tests to run and how to add a broker importer. Please report security problems
privately, as described in [SECURITY.md](SECURITY.md), not in a public issue.

## Who made this

**Original creator: Simon, a day trader, GitHub [simonro](https://github.com/simonro), publishing as Tape to Edge.** He built Trading-Journal-AI with Claude Code to make journaling easier. Libre Trading Journal is a derivative with additional integrations and data controls; the original work remains credited here and in Settings.

Simon's links: [YouTube @tapetoedge](https://www.youtube.com/@tapetoedge), [X @tapetoedge](https://x.com/tapetoedge), and [Tape to Edge newsletter](https://tape-to-edge.beehiiv.com).

Libre is maintained in [npcagomoc-del/libre-trading-journal](https://github.com/npcagomoc-del/libre-trading-journal). Report Libre issues here; the original project remains [simonro/Trading-Journal-AI](https://github.com/simonro/Trading-Journal-AI).

Educational software, not financial advice.

## License

MIT. See [LICENSE](LICENSE).

## Crypto, Forex and Gold sizing

Manual entry and generic CSV import accept `CRYPTO`, `FOREX`, and `GOLD`, including fractional quantities. Quantity means coins/base units/ounces when multiplier is 1. If your broker reports lots or contracts, enter its contract size in `multiplier`; do not enter lots while leaving that field at 1. Gold futures still use `FUTURE` with their point value.

All journal totals and commissions remain USD. `quote_currency` defaults to USD. For non-USD prices, supply `quote_to_usd_rate` (USD value of one quote-currency unit); no live conversion is guessed. Generic CSV conversion uses the final closing fill's supplied rate. Contract size and quote currency must stay consistent within a position. Execution edits retain the sizing fields.

These additions support journaling, import, filters and reports. Alpaca remains the stock-chart provider. Forex, gold and broker-supported crypto charts can use the local MT5 connection below.

Existing databases receive a transactional instrument-type migration, with a `.before-multi-asset.bak` backup alongside the database. Existing trades and IDs are retained.

## MT5 charts on Windows

Open the installed MetaTrader 5 desktop terminal and sign into your Exness, FTMO or FundedNext account there. In **More → Settings → Market data · MT5**, choose the journal account and matching price provider, then **Connect & test MT5**. Two connection methods are available:

- **MT5 MCP · built-in server:** In MT5, enable **Tools → Options → MCP → Enable internal server**. Enter its local address (usually `http://127.0.0.1:22346/mcp`) and access key in the journal's password field. The key is encrypted using Windows DPAPI under `%LOCALAPPDATA%\TradingJournalAI\mt5-mcp`, outside the OneDrive project; the journal database stores only an opaque credential reference. Reconnecting can reuse the saved key when the address is unchanged. The client restricts requests to account information, market-watch symbol information, chart history and time information, and accepts only localhost endpoints.
- **MT5 Python · desktop terminal:** Choose the installed `terminal64.exe`. This method uses the official MetaTrader5 Python package and the terminal's existing sign-in; it needs no journal API key or trading password.

The connector reads candles and tick volume; it does not place orders. It saves the connection and account identity per journal account and verifies that identity whenever it fetches prices. If you switch accounts in MT5, reconnect the journal deliberately or restore the saved account in MT5. Disconnecting removes the connection and its encrypted MCP credential, leaving trades intact.

Choose the clock used by the trade timestamps. Exness imports always use UTC+0. FTMO history uses UTC+2 or UTC+3 depending on the trade date; set the applicable offset when reviewing it. MCP additionally requires the **MT5 server clock for these dates** because its native candle timestamps use the broker clock. FundedNext uses UTC+3 in daylight time and UTC+2 in standard time; set the applicable historical offset when reviewing dates in another season. The connector converts candles to UTC, and the chart displays the chosen trade clock, including the actual execution date for overnight trades. FundedNext and FTMO candles are labelled as reference prices when reviewing Exness trades. Exact and unique broker suffixes are resolved; ambiguous symbols require the full Market Watch name.

Keep the terminal connected. Historical coverage depends on MT5 history, trading hours and the terminal's **Max. bars in chart** setting. Open the relevant chart in MT5 to download missing history. Forex tick volume is labelled explicitly; the stock-session VWAP is omitted for MT5 data. TradingView login and chart widgets are not needed for this feed.
