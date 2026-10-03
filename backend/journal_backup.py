"""Versioned, bounded journal archives. Never accesses credential stores or .env.

Call export/restore only while holding the application's exclusive journal lease.
The SQLite backup API includes committed WAL data and restores into the existing
database file. All untrusted extraction happens in a private staging directory.
"""
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

FORMAT_VERSION = 1
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_FILES = 10000
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.txt', '.csv', '.md'}
TABLE_COLUMNS = {
    'accounts': 'id name type color broker created_at',
    'trades': 'id account_id trade_group date ticker instrument_type side gross_pnl net_pnl commissions executions option_expiry option_strike option_type source imported_at swaps setup setup_grade setup_notes setup_features setup_source mfe_pct mae_pct exit_efficiency',
    'diary_entries': 'id account_id entry_date image_path raw_text ai_analysis created_at',
    'trade_analysis': 'id trade_group ticker date strategy stop_loss risk_per_trade risk_reward r_multiple entry_reason exit_reason mistakes emotional_state notes ai_feedback match_confidence match_notes diary_entry_id target_price trade_rating idea_source',
    'trade_tags': 'id trade_group tag_type tag_value source',
    'daily_summaries': 'id account_id summary_date ai_content generated_at',
    'settings': 'id account_id key value',
    'custom_setups': 'id name side notes active created_at',
    'library_items': 'id kind tag_type name description created_at',
    'library_aliases': 'id kind tag_type alias canonical created_at',
}
GOAL_FIELDS = {'win_rate', 'profit_factor', 'day_win_rate', 'expectancy', 'avg_win_loss_ratio', 'exit_efficiency'}
MT5_FIELDS = {'path', 'broker', 'login', 'server', 'utc_offset_hours', 'test_symbol', 'test_bars', 'transport', 'mcp_url', 'server_utc_offset_hours', 'credential_id'}
# Canonical DDL generated from database.init_db + init_library_tables on a
# disposable database. Update deliberately with schema changes/format versions.
SCHEMA_SIGNATURES = {
    'accounts': '51a51cfb733b0fbfadfc8c60e881d93c74ad2dc9a378d98d8856b5fd06c063fa',
    'custom_setups': '2fd9fdf114f58ea150323e462250da96aa612ba65bcd618b51fec39f73610cae',
    'daily_summaries': '18737355808dfaea8c8dfa0fbe6c48a9788c9b4c9bc6a16a7d7d80ede45208f3',
    'diary_entries': 'e1833aaccf4ca675e744f1ec2d7662e8391330c60c4fc58d77c19c58d0f4056f',
    'idx_analysis_group': '9ec4f9903d17c3307c6793daf62b14af13b8ce2fc12fa291a8bf90477fb95097',
    'idx_tags_group': 'ca9ba221b947dabff60d37435737667aa298c9c89430f4715e7f672fd469dbc9',
    'idx_trades_account_date': '6f2411392a016dac9debd9ed1260409ab34d0d51969ada0497cf2814c17bbe97',
    'idx_trades_group': 'a6e74802df733dc356ea7b8b2581ca7cda0c8571c46a86a76f2eb023938b9f45',
    'library_aliases': '0f1e0b77c1aebc9d58b02713206d70a1822b5ce1163812dc0c19a906ed4c1e03',
    'library_items': '56bb7fa113570b46fc54c09451f3a5e43cbdee440ad04f8f6f78963a7ce0934e',
    'settings': '9d7cd2b2dc033da8f10a09250c4c393ecd9c1e84143e22399c76a16d0e0c7459',
    'trade_analysis': '6fb79d0c98f0dd7fb7e2c6757dbf01cc388f8a58f2ef0a49a226b5c28bbf74c8',
    'trade_tags': '6c526566f8a271dfbd1180fab3a6be5c0b1be8f716f1c2ee7044d5ecafdb3fec',
    'trades': '63e202e79a71813b95bffc62b1410c2738eb5c6184954cd92b0db5526f0026fd',
}


def _schema_signature(sql):
    # Keep string literals exact, normalize SQLite's harmless table-name quotes
    # and whitespace, and ignore column order (old additive migrations differ).
    sql = re.sub(r'--[^\n]*', '', sql)
    tokens = re.findall(r"'(?:''|[^'])*'|[A-Za-z_][A-Za-z_0-9]*|[^\s\"]", sql)
    tokens = [token if token.startswith("'") else token.lower() for token in tokens]
    if tokens[:2] == ['create', 'table']:
        start = tokens.index('(')
        segments, current, depth = [], [], 0
        for token in tokens[start + 1:-1]:
            if token == ',' and depth == 0:
                segments.append(' '.join(current))
                current = []
            else:
                current.append(token)
                depth += (token == '(') - (token == ')')
        segments.append(' '.join(current))
        normalized = ' '.join(tokens[:start]) + ' (' + ','.join(sorted(segments)) + ')'
    else:
        normalized = ' '.join(tokens)
    return hashlib.sha256(normalized.encode()).hexdigest()


class BackupError(ValueError):
    pass


class RecoveryRequired(BackupError):
    """Rollback could not finish: stop normal requests until manual recovery."""
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def safe_attachment(name):
    if not isinstance(name, str) or not name or len(name) > 240 or name[0] == '.' or name[-1] in '. ':
        raise BackupError('Attachment filenames must be ordinary, non-hidden filenames.')
    if any(ord(c) < 32 or c in '/\\:<>"|?*' for c in name) or Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise BackupError('Unsupported or unsafe attachment filename in the journal.')
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        raise BackupError('Reserved attachment filename in the journal.')
    return name


def _json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise BackupError('Duplicate JSON property in backup.')
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(BackupError('Non-finite JSON value.')))
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise BackupError('Invalid JSON metadata or journal settings.') from exc


def validate_database(path):
    """Strict current schema and settings allowlists avoid importing hidden stores."""
    try:
        with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
            db.execute('PRAGMA trusted_schema=OFF')
            # Bound malformed/hostile database work as well as archive expansion.
            steps = [0]
            def limit():
                steps[0] += 1
                return steps[0] > 200000
            db.set_progress_handler(limit, 1000)
            all_schema = db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master').fetchall()
            schema = [(kind, name, sql) for kind, name, table, sql in all_schema
                      if name != 'sqlite_sequence' and not (kind == 'index' and name.startswith('sqlite_autoindex_') and table in TABLE_COLUMNS and sql is None)]
            tables = {name for kind, name, sql in schema if kind == 'table'}
            if tables != set(TABLE_COLUMNS) or any(kind not in {'table', 'index'} or 'VIRTUAL' in (sql or '').upper() for kind, name, sql in schema):
                raise BackupError('Backup has an unsupported database schema (tables, views or triggers).')
            if {name for kind, name, sql in schema} != set(SCHEMA_SIGNATURES) or any(not sql or _schema_signature(sql) != SCHEMA_SIGNATURES[name] for kind, name, sql in schema):
                raise BackupError('Backup schema constraints or indexes are incompatible with this app version.')
            sequence_schema = [(kind, sql) for kind, name, table, sql in all_schema if name == 'sqlite_sequence']
            if sequence_schema != [('table', 'CREATE TABLE sqlite_sequence(name,seq)')]:
                raise BackupError('Backup internal sequence schema is incompatible.')
            if any(name not in TABLE_COLUMNS or type(seq) is not int or seq < 0 for name, seq in db.execute('SELECT name,seq FROM sqlite_sequence')):
                raise BackupError('Backup contains unsupported internal sequence data.')
            for table, names in TABLE_COLUMNS.items():
                columns = db.execute(f'PRAGMA table_xinfo("{table}")').fetchall()
                if {row[1] for row in columns} != set(names.split()) or any(row[6] or row[2].upper() not in {'INTEGER', 'TEXT', 'REAL'} for row in columns):
                    raise BackupError('Backup database columns are incompatible with this app version.')
                if not any(row[1] == 'id' and row[2].upper() == 'INTEGER' and row[5] == 1 for row in columns):
                    raise BackupError('Backup database primary keys are incompatible.')
            expected_fks = {'trades': {('accounts', 'account_id', 'id')}, 'diary_entries': {('accounts', 'account_id', 'id')}, 'daily_summaries': {('accounts', 'account_id', 'id')}, 'trade_analysis': {('diary_entries', 'diary_entry_id', 'id')}}
            for table in TABLE_COLUMNS:
                keys = {(row[2], row[3], row[4]) for row in db.execute(f'PRAGMA foreign_key_list("{table}")')}
                if keys != expected_fks.get(table, set()):
                    raise BackupError('Backup database relationships are incompatible.')
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)] or db.execute('PRAGMA foreign_key_check').fetchone():
                raise BackupError('Backup database failed integrity or foreign-key validation.')
            for key, raw in db.execute('SELECT key,value FROM settings'):
                value = _json(raw)
                allowed = GOAL_FIELDS if key == 'goals' else MT5_FIELDS if key == 'mt5_market_data' else None
                if allowed is None or not isinstance(value, dict) or set(value) - allowed:
                    raise BackupError('Unsupported or potentially secret settings found. Export was refused without changing the journal.')
                if any(isinstance(v, (dict, list)) for v in value.values()):
                    raise BackupError('Nested or secret settings are not supported in journal backups.')
                if key == 'goals' and any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in value.values()):
                    raise BackupError('Goal settings must contain numbers only.')
                if value.get('credential_id') and not re.fullmatch('[0-9a-f]{32}', str(value['credential_id'])):
                    raise BackupError('MT5 credential reference is malformed; keys cannot be included in a backup.')
            attachments = {safe_attachment(row[0]) for row in db.execute('SELECT image_path FROM diary_entries WHERE image_path IS NOT NULL AND image_path != ""')}
            counts = {table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in ('accounts', 'trades', 'diary_entries')}
            return counts, attachments
    except sqlite3.Error as exc:
        raise BackupError('Backup database is invalid or incompatible.') from exc


def _snapshot(source, target):
    source = Path(source).resolve()
    if not source.is_file():
        raise BackupError('Journal database was not found. Verify the configured database path.')
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=10)) as src:
        with closing(sqlite3.connect(target, timeout=10)) as dst:
            src.backup(dst)
            dst.execute('PRAGMA journal_mode=DELETE')


def _digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'size': Path(path).stat().st_size, 'sha256': digest.hexdigest()}


def create_archive(db_path, upload_dir, destination):
    """Create a complete archive or fail explicitly; never silently omit files."""
    with tempfile.TemporaryDirectory(prefix='journal-export-') as temp:
        snapshot = Path(temp) / 'journal.sqlite3'
        _snapshot(db_path, snapshot)
        counts, referenced = validate_database(snapshot)
        # Remove deleted cells/free pages from the portable snapshot. This does
        # not alter the live database or any active journal rows.
        with closing(sqlite3.connect(snapshot)) as compact:
            compact.execute('VACUUM')
        files = {'journal.sqlite3': snapshot}
        upload_dir = Path(upload_dir)
        if upload_dir.is_symlink() or getattr(upload_dir, 'is_junction', lambda: False)() or (upload_dir.exists() and not upload_dir.is_dir()):
            raise BackupError('The upload directory must be an ordinary directory.')
        names = set()
        if upload_dir.exists():
            for path in upload_dir.iterdir():
                safe_attachment(path.name)
                if path.is_symlink() or not path.is_file() or getattr(path, 'is_junction', lambda: False)():
                    raise BackupError('Uploads contain a directory or linked file; backup was refused.')
                if path.name.casefold() in names:
                    raise BackupError('Uploads contain duplicate filenames for Windows.')
                names.add(path.name.casefold())
                files['uploads/' + path.name] = path
        if len(files) + 1 > MAX_FILES:
            raise BackupError('Too many files for a journal backup.')
        sizes = [path.stat().st_size for path in files.values()]
        if max(sizes) > MAX_FILE_BYTES or sum(sizes) > MAX_EXPANDED_BYTES:
            raise BackupError('Journal exceeds the supported backup size limits.')
        missing = sorted(referenced - {path.name for name, path in files.items() if name.startswith('uploads/')})
        manifest = {'format': 'libre-trading-journal', 'format_version': FORMAT_VERSION, 'created_at': now(), 'counts': counts,
                    'attachment_count': len(files) - 1, 'missing_attachments': missing,
                    'warnings': ['Some diary attachments are missing; this archive cannot be restored until repaired.'] if missing else [],
                    'files': {name: _digest(path) for name, path in files.items()}}
        with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, path in files.items():
                archive.write(path, name)
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        if Path(destination).stat().st_size > MAX_ARCHIVE_BYTES:
            Path(destination).unlink()
            raise BackupError('Compressed backup exceeds the supported size limit.')
        return manifest


def inspect_archive(source, staging):
    """Validate then extract a bounded archive into a caller-owned empty folder."""
    staging = Path(staging)
    if any(staging.iterdir()):
        raise BackupError('Backup staging directory must be empty.')
    if Path(source).stat().st_size > MAX_ARCHIVE_BYTES:
        raise BackupError('Backup file is too large (maximum 512 MiB).')
    try:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            if not 2 <= len(entries) <= MAX_FILES or sum(info.file_size for info in entries) > MAX_EXPANDED_BYTES:
                raise BackupError('Backup exceeds the file-count or expanded-size limit.')
            seen = set()
            for info in entries:
                name = info.filename
                if name not in {'manifest.json', 'journal.sqlite3'}:
                    if not name.startswith('uploads/'):
                        raise BackupError('Backup contains an unexpected file.')
                    safe_attachment(name[len('uploads/'):])
                if name.casefold() in seen or info.is_dir() or info.flag_bits & 1 or info.file_size > MAX_FILE_BYTES:
                    raise BackupError('Backup contains duplicate, encrypted or oversized files.')
                seen.add(name.casefold())
                mode = info.external_attr >> 16
                if stat.S_IFMT(mode) not in {0, stat.S_IFREG}:
                    raise BackupError('Backup contains a linked or non-regular file.')
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise BackupError('Unsupported ZIP compression.')
            if 'manifest.json' not in seen or 'journal.sqlite3' not in seen or archive.getinfo('manifest.json').file_size > 4 * 1024 * 1024:
                raise BackupError('Backup manifest or database is missing or oversized.')
            manifest = _json(archive.read('manifest.json'))
            if not isinstance(manifest, dict) or manifest.get('format') != 'libre-trading-journal' or type(manifest.get('format_version')) is not int or manifest['format_version'] != FORMAT_VERSION:
                raise BackupError('Unsupported journal backup format/version.')
            try:
                stamp = datetime.fromisoformat(manifest['created_at'])
                if stamp.tzinfo is None:
                    raise ValueError()
            except (KeyError, TypeError, ValueError):
                raise BackupError('Backup creation date is invalid.') from None
            files = manifest.get('files')
            if not isinstance(files, dict) or set(files) != {info.filename for info in entries if info.filename != 'manifest.json'}:
                raise BackupError('Backup manifest does not match its files.')
            for name, expected in files.items():
                info = archive.getinfo(name)
                if not isinstance(expected, dict) or expected.get('size') != info.file_size or not re.fullmatch('[0-9a-f]{64}', str(expected.get('sha256', ''))):
                    raise BackupError('Backup file metadata is invalid.')
                target = staging / name
                target.parent.mkdir(exist_ok=True)
                digest = hashlib.sha256()
                total = 0
                with archive.open(info) as src, target.open('xb') as dst:
                    for chunk in iter(lambda: src.read(1024 * 1024), b''):
                        total += len(chunk)
                        if total > info.file_size or total > MAX_FILE_BYTES:
                            raise BackupError('Backup file expanded beyond its declared size.')
                        digest.update(chunk)
                        dst.write(chunk)
                if total != info.file_size or digest.hexdigest() != expected['sha256']:
                    raise BackupError('Backup checksum does not match; the archive is damaged or changed.')
        counts, referenced = validate_database(staging / 'journal.sqlite3')
        present = {name[len('uploads/'):] for name in files if name.startswith('uploads/')}
        missing = sorted(referenced - present)
        if manifest.get('counts') != counts or manifest.get('attachment_count') != len(present) or manifest.get('missing_attachments') != missing:
            raise BackupError('Backup counts or attachment inventory do not match its database.')
        return {**manifest, 'warnings': ['Some diary attachments are missing; restore is disabled.'] if missing else []}
    except (zipfile.BadZipFile, KeyError, RuntimeError, NotImplementedError, EOFError) as exc:
        raise BackupError('Backup ZIP is invalid, incomplete or unsupported.') from exc


def recovery_directory():
    root = os.environ.get('LOCALAPPDATA')
    return Path(root) / 'TradingJournalAI' / 'backups' if root else Path.home() / '.local' / 'share' / 'TradingJournalAI' / 'backups'


def _replace_database(snapshot, live):
    # Existing inode and SQLite locking/WAL remain managed by SQLite itself.
    with closing(sqlite3.connect(Path(snapshot).resolve().as_uri() + '?mode=ro', uri=True, timeout=10)) as src:
        with closing(sqlite3.connect(Path(live).resolve().as_uri() + '?mode=rw', uri=True, timeout=10)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise BackupError('Restored database failed its integrity check.')


def restore_archive(source, db_path, upload_dir, recovery_dir=None):
    db_path, upload_dir = Path(db_path).resolve(), Path(upload_dir).absolute()
    recovery_dir = Path(recovery_dir) if recovery_dir else recovery_directory()
    with tempfile.TemporaryDirectory(prefix='journal-inspect-') as temp:
        staged = Path(temp)
        manifest = inspect_archive(source, staged)
        if manifest['missing_attachments']:
            raise BackupError('Restore refused because the backup has missing diary attachments.')
        if upload_dir.is_symlink() or getattr(upload_dir, 'is_junction', lambda: False)():
            raise BackupError('Restore does not support linked upload directories.')
        if db_path == upload_dir or upload_dir.resolve() in db_path.parents:
            raise BackupError('The database must be outside the uploads directory.')
        recovery_dir.mkdir(parents=True, exist_ok=True)
        recovery_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex
        recovery_path = recovery_dir / (recovery_id + '.zip')
        partial = recovery_dir / (recovery_id + '.partial')
        try:
            recovery_manifest = create_archive(db_path, upload_dir, partial)
            if recovery_manifest['missing_attachments']:
                raise BackupError('Restore refused because the current journal has missing diary attachments and its recovery backup would be incomplete.')
            os.replace(partial, recovery_path)
        finally:
            partial.unlink(missing_ok=True)
        # Separate unsanitized snapshot for byte-faithful rollback; recovery ZIP
        # has already passed the same strict no-secret checks as an export.
        previous_db = staged / 'previous.sqlite3'
        _snapshot(db_path, previous_db)
        upload_dir.parent.mkdir(parents=True, exist_ok=True)
        working = Path(tempfile.mkdtemp(prefix='.journal-restore-', dir=upload_dir.parent))
        incoming, previous = working / 'incoming', working / 'previous'
        shutil.copytree(staged / 'uploads', incoming) if (staged / 'uploads').exists() else incoming.mkdir()
        moved_previous = installed = db_started = False
        succeeded = False
        try:
            if upload_dir.exists():
                os.replace(upload_dir, previous)
                moved_previous = True
            os.replace(incoming, upload_dir)
            installed = True
            db_started = True
            _replace_database(staged / 'journal.sqlite3', db_path)
            succeeded = True
        except BaseException as original:
            try:
                if db_started:
                    _replace_database(previous_db, db_path)
                if installed:
                    os.replace(upload_dir, working / 'failed-incoming')
                if moved_previous:
                    os.replace(previous, upload_dir)
            except BaseException as rollback:
                raise RecoveryRequired(f'Restore and rollback could not finish. Stop the app and recover from backup {recovery_id}; upload recovery is retained at {working}.') from rollback
            raise BackupError(f'Restore failed; the previous journal was restored. Recovery backup: {recovery_id}.') from original
        finally:
            # Keep previous uploads whenever rollback did not complete. Every
            # recursively removed path is a uniquely created staging directory.
            if succeeded or not previous.exists():
                shutil.rmtree(working)
        return {'restored': True, 'recovery_backup': {'id': recovery_id, 'created_at': recovery_manifest['created_at']},
                'counts': manifest['counts'], 'restart_required': False}


def recovery_path(identifier, directory=None):
    if not re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{32}', identifier):
        raise BackupError('Invalid recovery backup ID.')
    path = (Path(directory) if directory else recovery_directory()) / (identifier + '.zip')
    if path.is_symlink() or not path.is_file():
        raise BackupError('Recovery backup was not found.')
    return path


def list_recovery(directory=None):
    folder = Path(directory) if directory else recovery_directory()
    result = []
    if folder.exists():
        for path in sorted(folder.glob('*.zip'), reverse=True):
            if path.is_symlink() or not re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{32}', path.stem):
                continue
            try:
                stamp = datetime.strptime(path.stem.split('-')[0], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).isoformat(timespec='seconds')
            except ValueError:
                continue
            result.append({'id': path.stem, 'created_at': stamp})
    return {'backups': result}
