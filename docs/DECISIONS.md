# Design decisions and implementation constraints

Recorded from code/documentation through **2026-10-04**. This describes current design and explicit user requirements. Rationale below is stated by code/docs or identified as an inference. Revisit deliberately when requirements change.

| Decision | Evidence and practical consequence |
|---|---|
| Local journal with SQLite | `database.py`, `launch.bat`: local DB, WAL and loopback startup. Simple single-user operation; current-directory/configuration matters and backups must be consistent. Do not treat it as a shared cloud database. |
| Deterministic accounting | `instruments.py`, parsers, manual/execution calculations and tests. AI is optional coaching, not the source of trade reconstruction or P&L. Money changes require numerical regression coverage. |
| Explicit quantities/currencies | Multi-asset sizing requires multiplier and explicit non-USD rate. No exchange-rate guess. Inference: this favors inspectable arithmetic over automatic but potentially incorrect historical conversion. |
| Separate Exness position import | `exness_parser.py` receives completed tickets and uses broker profit; generic parser receives fills. Combining their shapes would lose ticket identity or overwrite broker results. Preserve this distinction. |
| Account-scoped repeat imports | Fingerprints/grouping in `csv_parser.py`, ticket IDs in `exness_parser.py`, `(trade_group, account_id)` uniqueness. Reimport aims to update/skip rather than duplicate, while preserving review metadata. |
| Refuse malformed input | Parser validation and line errors. Individual database write failures currently have partial-success behavior; this is a limitation, not a blanket atomic-import guarantee. |
| Backward-compatible multi-asset migration | `migrate_asset_types` backs up then transactionally rebuilds the CHECK constraint, preserving columns/IDs. Do not replace the user's database with a fresh schema. |
| ChatGPT plan OAuth | `chatgpt_provider.py`, `chatgpt_routes.py`: no API-key billing fallback, dynamic model access, local guards, Windows DPAPI and completed-stream verification. Keep authentication and inference verification distinct. |
| Explicit AI choice (4 October) | User requested ChatGPT sign-in, OpenAI API, Claude API and OpenRouter. Shared dispatch keeps existing OAuth and saved API configurations separate; no automatic paid provider switch. Keys are installation credentials, not journal data. OpenRouter Claude uses OpenRouter's full model slug/key. |
| Versioned journal ZIP (4 October) | User requested backup/restore. SQLite snapshot + attachments + checksums; current-schema validation; all-account replacement with exact RESTORE, automatic recovery and rollback. Single-process request gate prevents in-app writes during a snapshot. Conservative compatibility favors visible failure over silent loss. No automatic backup schedule. |
| Libre naming and upstream credit (4 October) | User named the derivative Libre Trading Journal and requested original creator credit. Header/Settings/docs retain Simon / simonro / Tape to Edge and MIT copyright. Internal credential-directory names stay TradingJournalAI to preserve existing connections. Local changes are not publication. |
| Credentials outside OneDrive checkout | Windows ChatGPT and MCP stores are under LocalAppData; MT5 config contains only a credential reference. Inference: separation reduces accidental source-control/sync exposure of credential blobs. It does not encrypt the journal DB itself. |
| Read-only MT5 integration | Python/MCP routes read account identity, symbols and candles; MCP tool allowlist restricts tools. An account mismatch fails instead of silently changing the feed. Preserve absence of order placement. |
| Explicit historical chart clocks | Trade clock and MCP server clock are separate; Exness trade metadata selects UTC+0. Provider and season affect historical alignment. Do not infer timezone from the user's computer. |
| Optional market data | Core journal works without charts. Alpaca is the stock source; configured MT5 serves forex/gold/crypto; some futures use stock proxies. Missing/unsupported data returns warnings, not fabricated candles. |
| Library aliases after merge | `library.py`: renames/merges update trade analysis/tags and aliases normalize future diary output. Effects can span accounts; back up before broad cleanup. |
| React state navigation and chat | `App.js`, `Brain.js`: no router-backed page URLs or persistent Brain chat history. Reload resets page/session state while journal data remains in SQLite. |

Future decisions should record: problem, chosen behavior, alternatives/tradeoff, affected data/API/UI, evidence/tests and date. Mark proposals as proposals until implemented or explicitly accepted. See [status](PROJECT-STATUS.md) for unresolved choices and [changelog](CHANGELOG.md) for actual history.
