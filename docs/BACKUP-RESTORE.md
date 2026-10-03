# Backup and restore your journal

Use **More → Settings → Backup & restore**. The built-in controls operate on the entire journal, including all accounts. A downloaded backup contains private trading data; keep it somewhere you trust. There is no automatic scheduled backup in this version.

## Download a backup

1. Finish any ongoing imports or AI analysis.
2. Open **Backup & restore** and click **Download backup**.
3. Wait for the ZIP download. Save a copy on another protected device/location if you need protection against losing this computer or disk.
4. Select that ZIP under **Restore a backup** and use **Check backup** to verify it and review counts without restoring anything.

The archive contains a consistent SQLite snapshot, diary attachments (including ordinary orphaned uploaded files), and a versioned manifest with file sizes/checksums and record counts. Committed WAL data is included using SQLite's backup API. It does not include the application source, original broker CSV exports stored elsewhere, API keys, OAuth tokens, MT5 encrypted keys, or .env configuration.

If the current journal already references missing attachments, the exported archive reports them when checked and cannot be restored until repaired. Unsupported files, secret-like settings, or incompatible schemas fail explicitly rather than being silently excluded. Fix the exact cause; do not delete journal records just to bypass a backup error.

## Restore a backup

**Restore replaces all accounts, trades, diary entries, settings and uploaded attachments in this journal. It does not merge two journals.** Installation AI credentials and active provider selection remain separate.

1. Finish work in other journal tabs. Download a fresh current backup as an additional precaution.
2. Select the intended ZIP and click **Check backup**. Review its creation time, account/trade/diary counts, attachments and warnings.
3. Missing attachments disable restore. Invalid archives are rejected before live journal paths are changed.
   Restore is also refused if the **current** journal is missing referenced attachments, because its automatic recovery copy would be incomplete. Recover those files before proceeding; preserve the database and remaining uploads while investigating.
4. When the preview matches the snapshot you want, type **RESTORE** exactly.
5. Click **Replace journal & restore** once and wait. The system first saves a recovery ZIP of the previous journal.
6. On success, click **Reload journal**. Review restored accounts, a known date's trade results and diary attachments. Reload any other open journal tabs so they discard stale records/forms.
7. Keep the recovery backup until satisfied. **Download previous journal** gives you the pre-restore snapshot immediately; **Saved recovery copies** also lists it after a page reload.

The backend does not require a restart for a successful restore. After moving to a different machine or Windows user, reconnect AI and MT5 services. Their private credentials are deliberately not portable in the journal ZIP.

## Recovery if restore fails

The server validates/stages the uploaded archive, retains a pre-restore ZIP, stages matching uploads, then restores the SQLite snapshot through SQLite itself. If applying the restore fails, it attempts to roll back both database and uploads. Do not repeat restore blindly; read the result.

- **Previous journal was restored:** inspect the current journal, download the recovery copy, and resolve the reported disk/permission problem before retrying.
- **Restore and rollback could not finish:** stop using the journal. The message identifies the recovery ZIP and retained upload recovery directory. Keep both. Ordinary journal requests return 503 while this server is in recovery mode; recovery list/download endpoints remain available. Follow the [advanced manual recovery steps](DATA-GUIDE.md#restore-without-losing-the-current-state) with the maintainer/AI using the real configured paths. A restart clears the process gate, so complete recovery before restarting normal use.
- **No space / permissions:** do not remove the only recovery copy. Free space elsewhere or resolve folder permissions, then validate the backup again.

Recovery ZIPs are stored outside the checkout under `%LOCALAPPDATA%\TradingJournalAI\backups\` on Windows. The fallback location is `~/.local/share/TradingJournalAI/backups/`. They contain private journal data, not service credentials. They remain until you manage them yourself; the app does not automatically delete old recovery copies. Downloads are offered in Settings.

## Supported operation and limits

- Use **one backend process/worker** for this local journal. During export/restore, the server waits for ordinary journal requests to finish and temporarily holds new requests until the operation is done, including streamed-response/dependency cleanup.
- Other SQLite tools, other backend processes, and OneDrive synchronization are outside that request lock. Stop those writers/sync activity when necessary; this is not a shared multi-computer database feature.
- Only this app's versioned ZIP backup format is accepted. A plain .db file or arbitrary ZIP is not a built-in restore archive; use the documented manual process where appropriate.
- Limits: ZIP up to 512 MiB, total expanded files up to 1 GiB, any single file up to 256 MiB, and at most 10,000 entries. Larger journals need an advanced backup process.
- Current table/column relationships must match this implementation. Archives with unknown tables, views/triggers, unsupported settings or unsafe attachment paths are refused. Future schema changes must include deliberate backup-version compatibility work.
- Checksums detect accidental or changed contents; they do not prove the financial calculations are correct or that a backup came from a trusted person. Keep your own original broker statements.

## Implementation references

[journal_backup.py](../backend/journal_backup.py) creates/validates archives and performs recovery, [backup_routes.py](../backend/backup_routes.py) adds local-only download/check/restore endpoints, [journal_maintenance.py](../backend/journal_maintenance.py) coordinates requests, and [BackupRestore.js](../frontend/src/components/BackupRestore.js) presents the controls. Automated tests and the visual check use disposable synthetic journals, never the user's real database.
