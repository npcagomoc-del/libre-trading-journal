# User guide

This guide follows **Libre Trading Journal**, updated **4 October 2026 (Asia/Manila)**. Built on Trading-Journal-AI by Simon / simonro / Tape to Edge, with the original MIT credit retained. Examples below are synthetic. Hindi kailangan ng AI connection para mag-import, mag-record, at makita ang trading results.

## 1. Open and close the journal

1. Open the extracted or cloned app folder containing `setup.bat`, `backend`, and `frontend`. For a new PC, follow [Windows installation](INSTALL-WINDOWS.md). In the original development workspace, the app folder is `Trading-Journal-AI`.
2. For a first installation, run `setup.bat` once. You need Python 3.11+ and Node.js with npm; the repository CI uses Node 24. [Manual setup](DEVELOPER-GUIDE.md#setup-on-windows) is available if setup fails.
3. Run `launch.bat`. It starts a backend terminal and a frontend terminal. Keep both open.
4. Wait until the backend reports application startup complete and the frontend finishes compiling.
5. Open [http://localhost:3010](http://localhost:3010). Port 8010 is the API, not the journal interface.
6. To stop, press **Ctrl+C** in each server terminal and answer the terminal's stop prompt if shown. Closing the browser alone does not stop the servers.

If nothing opens, or you see a blank/empty page unexpectedly, use [startup recovery](TROUBLESHOOTING.md#start-here-when-the-app-will-not-open). Keep the error visible; reinstalling is usually not the first step.

## 2. Create and select a journal account

1. Open **All Accounts** in the top bar.
2. Choose **New Account** and enter a recognizable name, such as `Exness Demo` or `Live Forex`.
3. Choose account type (Day Trading, Swing Trading or Investment) and color, then click **Create**. The current form has no broker selector; choose the actual broker explicitly on Import.
4. Select that account in the top bar. **All Accounts** combines accounts in the views; importing and adding trades require a specific destination account.
5. Use the pencil beside an account to rename it.

A journal account is a local grouping of records. Creating it does not sign into a broker, import trade history automatically, or connect prices. Keep demo and real accounts separate. Check the **Account** field again on Import even after choosing an account in the header.

## 3. Import Exness / MT5 forex and gold history

1. Export your closed positions from the broker. Keep the original file as your source of truth.
2. Open **Import** in the top bar. Choose your journal account and **Exness / MT5 (Forex & Gold)**.
3. Download the **blank template** and **example** shown below the importer. If the export does not match, copy the completed positions into the template.
4. Use **one row per fully closed ticket**, containing open and close timestamps, both prices, side, fractional lots and broker Profit. Native MT5 HTML reports, separate order/deal rows and partial closes sharing a ticket are unsupported.
5. Keep `commission` negative for a charge and keep the sign of `swap`. Blank charges mean zero. Use real broker contract sizes; XAUUSD defaults to 100 ounces per lot and forex to 100,000 base units per lot.
6. USD is the money default. For another account currency, supply `account_currency` and `account_to_usd_rate` (USD per one account-currency unit). Convert cent-account money to standard units first.
7. Keep timestamps in the original broker clock. Reports place the trade on its **closing date**. Do not change imported timestamps to Philippine time just to match your computer.
8. Select/drop the CSV and click **Import Trades**. Read the result, including skipped duplicates and any DB errors.
9. Open **Trade View**, clear date filters if necessary, and inspect a few trades against the broker statement: ticket, symbol, lots, prices, gross profit, commission, swap and net profit.

Synthetic example: broker profit `$16.17`, commission `-$0.33`, swap `$0.00` gives net `$15.84`. See the [data guide](DATA-GUIDE.md#exness-position-format) for fields and rounding.

Repeat imports into the **same journal account** skip identical tickets. Corrected rows update those tickets while retaining existing analysis and tags. Correct Exness prices/lots in the CSV and reimport; the execution editor restricts those changes to preserve broker-reported profit. A different journal account has its own ticket scope.

## 4. Import other brokers

Choose Thinkorswim account statement CSV or IBKR Activity Statement CSV for their dedicated formats. **Auto-detect** attempts to identify supported headers.

For an unsupported broker, choose **Other broker (generic template)** and download its template/example. This format uses **one row per fill**, unlike the Exness position template. Include each buy and sell; the app reconstructs round trips, partial fills and scale-ins.

Required columns are `date,time,symbol,side,quantity,price`. Use unambiguous ISO dates (`2026-10-02`), positive quantities and correct instruments/multipliers. Generic commissions are USD costs, not Exness signed commission values. The [data guide](DATA-GUIDE.md#generic-execution-format) lists optional fields.

If parsing fails, fix the reported line in a copy of the file and retry. A parsing error occurs before import writes; **DB errors after parsing can mean partial success**, so review the result before retrying. Never delete all existing trades to resolve a duplicate warning.

## 5. Add a trade manually

1. Click **Add Trade**.
2. Select the account, ticker, date, optional time, instrument type and Long/Short side.
3. Enter entry price, exit price (leave blank for an open position), quantity and commissions in USD.
4. For crypto/forex/gold, set **Units per quantity / contract** correctly. With multiplier 1, quantity means coins, base currency units or ounces. For forex lots use the broker's units per lot; for gold lots use ounces per lot. For futures use the contract's point value.
5. If the price is quoted in a non-USD currency, enter the quote currency and USD conversion rate. The app does not fetch an exchange rate for this calculation.
6. Add strategy, stop loss and notes if useful, then **Save Trade**.
7. Open the saved trade in **Trade View** and verify the calculation.

For example, a synthetic long gold position of `0.10` lots, contract size `100`, entry `2300`, exit `2310` has gross profit `$100`; a `$0.20` commission makes net `$99.80`. These are arithmetic examples, not trading recommendations.

For richer option metadata, use the generic CSV fields. The current Add Trade modal exposes the asset selector but does not provide all option-contract fields.

## 6. Review and annotate

- **Dashboard:** choose account and period; inspect net P&L, equity, session strip, goals, recent trades and breakdowns. An equity curve represents journal P&L, not deposits or the live broker account balance.
- **Trade View:** filter ticker, type and From/To dates, sort columns, and click a trade row. Check execution dates/times, quantities, fees, gross/net results and notes.
- **Trade Details:** review/edit analysis fields and tags, choose a playbook setup, and use execution controls where available. Manual edits and deletes affect the saved journal; make a backup before bulk cleanup. Exness import restrictions are intentional.
- **Calendar:** choose a trading day to open its **Day Review**.
- **Day Review:** check the date first; the app initially selects the most recent trading day. Review session statistics and request an AI review only when connected. AI grading evaluates process and may criticize a profitable trade.
- **Reports:** select the appropriate period and breakdown/tab. Compare numeric tables as well as bars; rows with few trades provide limited evidence. See [calculation caveats](DATA-GUIDE.md#metrics-and-interpretation) before expecting every summary to use an identical denominator.

Missing chart/AI results do not mean your imported trades failed to save. Stored R, grades and diary feedback can be entered or generated analysis; they are not all independently recomputed financial facts.

## 7. Add a diary and use the AI coach

### Choose your AI provider

Open **More → Settings → Your AI, your choice** and choose **ChatGPT sign-in**, **OpenAI API key (ChatGPT API)**, **Claude API key**, or **OpenRouter API key**. This selection applies to Brain, diary analysis, insights, and reviews. Other saved connections remain available when you switch.

For an API choice, paste the matching service's key, choose/enter its **Model ID**, then **Save settings**. Use **Refresh models** for suggestions and **Test connection** to verify access; the test can incur API charges. A ChatGPT subscription does not include OpenAI API billing. Your OpenRouter Claude key belongs under **OpenRouter**, with its full model slug. Leave the key blank to retain it when changing the model. See the [complete provider tutorial](AI-PROVIDERS.md).

### Connect ChatGPT

1. In the AI provider dropdown, select **ChatGPT sign-in**.
2. Choose **Continue with ChatGPT**. Complete sign-in in the browser window and approve plan usage if offered.
3. Return to the journal, choose an available model and click **Test connection**.
4. Look for **Verified: ChatGPT completed a response.** Signing in by itself is not proof that coaching works.

ChatGPT sign-in uses the existing plan OAuth connection and never automatically switches to API billing. Available models, eligibility and limits come from your account at runtime. Use **Manage ChatGPT usage** to inspect account controls; keep optional paid-credit permission disabled if you do not want spending beyond plan usage. Testing and coaching can consume usage. The user reports this connection works; this development pass did not retest live inference.

### Import diary material

1. Import that day's trades first so the analysis can match them.
2. On **Import → Analyze Trading Diary**, choose a supported image (`png`, `jpg`, `jpeg`, `webp`, `gif`, `heic`, `heif`) or UTF-8 `.txt`/`.csv` note. Images require an image-capable selected model. HEIC/HEIF conversion dependencies are included; if a photo fails conversion, export JPEG/PNG and retry.
3. Choose the date and account, then **Analyze Diary**.
4. Open **Diary**, expand the date/entry and review the extracted feedback and trade matches. Check ambiguous matches and correct analysis on the trade where needed.
5. If you see **Diary saved, but AI analysis failed**, the file and diary row already exist. Inspect Diary before uploading again; another upload creates another entry. There is no dedicated retry-analysis button in the current Diary page.

Diary deletion removes the entry record and unlinks its trade analysis; the trade analysis remains. Uploaded files are not automatically removed by those delete endpoints. **Delete all diary entries for a date** follows the selected account; under All Accounts it can affect every account on that date.

### Brain and reviews

Open **Brain** in the top bar and check its provider/model status. If setup is needed, its Settings button takes you to the connection controls. Ask a focused question, such as “Which mistakes repeat in this account's recorded trades?” Check the selected account and verify important statements against Trade View/Reports. Brain receives journal context needed for the answer. Its chat messages are held in browser memory and are lost on page reload; copy useful answers into your own notes. Stored reviews are not automatically regenerated by switching providers.

## 8. Connect MT5 price charts (optional, Windows)

1. Open the MT5 terminal and sign into the intended trading account there.
2. Open **More → Settings → Market data · MT5**. Select the journal account and the actual price provider: FundedNext, FTMO or Exness.
3. Choose one connection method:
   - **MT5 MCP · built-in server:** if your terminal offers **Tools → Options → MCP**, enable its internal server. Enter its localhost `/mcp` address and access key. The UI defaults to `http://127.0.0.1:22346/mcp`. If your terminal lacks that option, use the Python method.
   - **MT5 Python · desktop terminal:** choose the installed `terminal64.exe`; it uses the terminal's existing sign-in.
4. Enter a symbol available in that account's Market Watch, including its suffix when needed.
5. Set **Trade timestamp clock** to the clock of your recorded trades. Exness imported trades use UTC+0 automatically. Choose UTC+8 only for records actually written in Philippine time.
6. For MCP, also set **MT5 server clock for these dates** to the provider's historical clock. The UI offers UTC+0/+2/+3; verify the applicable date with your terminal/broker rather than using today's seasonal offset for all history.
7. Click **Connect & test MT5**, then open a forex/gold/supported crypto trade and inspect its chart. Keep MT5 connected.

The journal reads prices and account identity; it does not place orders. Prices from FTMO/FundedNext may be a reference for Exness trades and can differ from execution prices. Changing the signed-in MT5 account can trigger an identity mismatch until you intentionally reconnect. [Chart troubleshooting](TROUBLESHOOTING.md#mt5-and-other-chart-errors) covers missing candles and wrong clocks.

Stock charts use optional Alpaca credentials in `backend/.env`; restart the backend after changing them. Some futures charts use ETF proxies, not actual futures candles.

## 9. Keep names and data organized

In **More → Settings**, the **Strategies**, **Sources** and **Tags** tabs support adding, renaming, merging and deleting library names. These operations can update every trade using the name, across accounts; review the affected count and back up before broad changes. A merge remembers an alias so later diary analysis can use the canonical name. A library strategy and a trade's playbook setup are related concepts but are stored separately; inspect both when normalizing old records.

## 10. Back up and restore

1. Open **More → Settings → Backup & restore**, then **Download backup**. Keep the ZIP private and save a protected copy away from this computer.
2. To verify it, select the ZIP and click **Check backup**. Review the date, counts, attachments and warnings; checking does not restore anything.
3. To replace the journal, choose the intended ZIP, check it, type **RESTORE**, then **Replace journal & restore**. This replaces **every account**, rather than merging records.
4. The system saves an automatic recovery copy first. After success, **Reload journal** and review a known trade/date and diary attachment. **Download previous journal** and **Saved recovery copies** give you the prior snapshot.

Backups exclude API keys, sign-in tokens and .env. Reconnect services on a new machine. Missing attachments block restore, and a failed operation reports recovery steps. Follow the [full backup tutorial](BACKUP-RESTORE.md); the [data guide](DATA-GUIDE.md#backup-a-consistent-journal) covers advanced offline recovery. No recurring backup schedule is configured.

A good daily routine is: select the account → import → reconcile results → add diary/notes → review → back up. The [status checkpoint](PROJECT-STATUS.md) lists current limitations and the next useful maintenance work.
