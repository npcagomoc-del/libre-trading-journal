import asyncio
import json
import sqlite3
import sys
import zipfile
from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backup_routes
import database
import journal_backup as backup
import journal_maintenance
import library
from journal_maintenance import JournalGate, JournalMaintenanceMiddleware


@pytest.fixture
def journal(tmp_path, monkeypatch):
    db = tmp_path / 'live.sqlite3'
    uploads = tmp_path / 'uploads'
    uploads.mkdir()
    recovery = tmp_path / 'recovery'
    monkeypatch.setattr(database, 'DB_PATH', str(db))
    database.init_db()
    with closing(database.get_db()) as conn:
        library.init_library_tables(conn)
        conn.execute("INSERT INTO accounts(name,type) VALUES('Synthetic','day_trading')")
        conn.execute("INSERT INTO trades(account_id,trade_group,date,ticker,instrument_type,side,net_pnl) VALUES(1,'sample','2026-10-01','TEST','STOCK','LONG',12.5)")
        conn.execute("INSERT INTO diary_entries(account_id,entry_date,image_path) VALUES(1,'2026-10-01','note.txt')")
        conn.execute("INSERT INTO trade_analysis(trade_group,ticker,date,notes,diary_entry_id) VALUES('sample','TEST','2026-10-01','Preserve this note',1)")
        conn.execute("INSERT INTO settings(account_id,key,value) VALUES(0,'goals','{\"win_rate\":65}')")
        conn.execute("INSERT INTO library_items(kind,name) VALUES('strategy','Breakout')")
        conn.execute("INSERT INTO library_aliases(kind,alias,canonical) VALUES('strategy','BO','Breakout')")
        conn.commit()
    (uploads / 'note.txt').write_text('Synthetic diary', encoding='utf-8')
    (uploads / 'orphan.png').write_bytes(b'synthetic image')
    return db, uploads, recovery


def make_archive(journal, tmp_path):
    target = tmp_path / 'backup.zip'
    backup.create_archive(journal[0], journal[1], target)
    return target


def inspect(source, tmp_path):
    staging = tmp_path / 'inspection'
    staging.mkdir()
    return backup.inspect_archive(source, staging)


def rewrite(source, mutation):
    with zipfile.ZipFile(source) as archive:
        contents = {item.filename: archive.read(item) for item in archive.infolist()}
    mutation(contents)
    with zipfile.ZipFile(source, 'w') as archive:
        for name, value in contents.items():
            archive.writestr(name, value)


def test_complete_roundtrip_wal_and_recovery(journal, tmp_path):
    db, uploads, recovery = journal
    # Keep a connection alive with a committed WAL frame, proving plain .db
    # copying would not provide a complete snapshot.
    with closing(database.get_db()) as conn:
        conn.execute("UPDATE trades SET net_pnl=98.75")
        conn.commit()
        assert Path(str(db) + '-wal').exists()
        archive = make_archive(journal, tmp_path)
        manifest = inspect(archive, tmp_path)
        assert manifest['counts'] == {'accounts': 1, 'trades': 1, 'diary_entries': 1}
        assert manifest['attachment_count'] == 2
        conn.execute("UPDATE accounts SET name='Before restore'")
        conn.execute("UPDATE trades SET net_pnl=-42")
        conn.commit()
        (uploads / 'note.txt').write_text('Before restore')
        (uploads / 'later.md').write_text('Preserve via recovery')
        result = backup.restore_archive(archive, db, uploads, recovery)
        # An already-open idle SQLite connection sees the replacement safely.
        assert conn.execute('SELECT net_pnl FROM trades').fetchone()[0] == 98.75
        assert conn.execute('SELECT notes FROM trade_analysis').fetchone()[0] == 'Preserve this note'
        assert conn.execute('SELECT canonical FROM library_aliases').fetchone()[0] == 'Breakout'
    assert (uploads / 'note.txt').read_text() == 'Synthetic diary'
    assert not (uploads / 'later.md').exists()
    assert (uploads / 'orphan.png').exists()
    assert result['restart_required'] is False
    recovery_file = backup.recovery_path(result['recovery_backup']['id'], recovery)
    backup.restore_archive(recovery_file, db, uploads, recovery)
    with closing(database.get_db()) as conn:
        assert conn.execute('SELECT net_pnl FROM trades').fetchone()[0] == -42
    assert (uploads / 'later.md').read_text() == 'Preserve via recovery'


def test_separate_credentials_never_archived(journal, tmp_path):
    (tmp_path / '.env').write_text('NEVER_EXPORT_THIS=secret')
    vault = tmp_path / 'chatgpt'
    vault.mkdir()
    (vault / 'connection.bin').write_bytes(b'private login')
    with closing(database.get_db()) as conn:
        config = {'credential_id': 'a' * 32, 'transport': 'mcp', 'mcp_url': 'http://127.0.0.1:22346/mcp', 'login': '1234'}
        conn.execute('INSERT INTO settings(account_id,key,value) VALUES(1,?,?)', ('mt5_market_data', json.dumps(config)))
        conn.commit()
    archive = make_archive(journal, tmp_path)
    with zipfile.ZipFile(archive) as contents:
        assert set(contents.namelist()) == {'journal.sqlite3', 'manifest.json', 'uploads/note.txt', 'uploads/orphan.png'}
        assert b'NEVER_EXPORT_THIS' not in contents.read('journal.sqlite3')


def test_csv_attachment_roundtrip(journal, tmp_path):
    (journal[1] / 'notes.csv').write_text('date,note\n2026-10-01,Synthetic')
    archive = make_archive(journal, tmp_path)
    manifest = inspect(archive, tmp_path)
    assert manifest['attachment_count'] == 3
    (journal[1] / 'notes.csv').unlink()
    backup.restore_archive(archive, *journal[:2], journal[2])
    assert (journal[1] / 'notes.csv').read_text().startswith('date,note')


def test_changed_constraint_with_same_columns_is_refused(journal, tmp_path):
    with closing(database.get_db()) as conn:
        conn.execute('PRAGMA writable_schema=ON')
        conn.execute("UPDATE sqlite_master SET sql=replace(sql, 'DEFAULT 1', 'DEFAULT 2') WHERE name='custom_setups'")
        conn.commit()
    with pytest.raises(backup.BackupError, match='schema constraints'):
        make_archive(journal, tmp_path)


def test_archive_removes_deleted_secret_cells(journal, tmp_path):
    # Historical deleted values are absent even when secure_delete was disabled.
    marker = 'SYNTHETIC_DELETED_SECRET_' * 100
    with closing(database.get_db()) as conn:
        conn.execute('PRAGMA secure_delete=OFF')
        conn.execute('INSERT INTO settings(account_id,key,value) VALUES(0,?,?)', ('old_key', marker))
        conn.commit()
        conn.execute("DELETE FROM settings WHERE key='old_key'")
        conn.commit()
    archive = make_archive(journal, tmp_path)
    with zipfile.ZipFile(archive) as contents:
        assert marker.encode() not in contents.read('journal.sqlite3')


@pytest.mark.parametrize('key,value', [('api_key', '"secret"'), ('mt5_market_data', '{"api_key":"secret"}'), ('goals', '{"win_rate":"secret"}')])
def test_secret_or_unknown_settings_refused(journal, tmp_path, key, value):
    with closing(database.get_db()) as conn:
        conn.execute('INSERT OR REPLACE INTO settings(account_id,key,value) VALUES(0,?,?)', (key, value))
        conn.commit()
    with pytest.raises(backup.BackupError):
        make_archive(journal, tmp_path)


@pytest.mark.parametrize('filename', ['../escape.txt', 'uploads/../escape.txt', '/absolute.txt', 'uploads/a:stream.txt', 'uploads/nul.txt', '.env', 'uploads/.env.txt', 'uploads/dir/file.txt'])
def test_unsafe_archive_paths_rejected(journal, tmp_path, filename):
    archive = make_archive(journal, tmp_path)
    with zipfile.ZipFile(archive, 'a') as contents:
        contents.writestr(filename, 'bad')
    with pytest.raises(backup.BackupError):
        inspect(archive, tmp_path)


def test_duplicate_symlink_and_size_limits(journal, tmp_path, monkeypatch):
    archive = make_archive(journal, tmp_path)
    with zipfile.ZipFile(archive, 'a') as contents:
        info = zipfile.ZipInfo('uploads/link.txt')
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        contents.writestr(info, 'note.txt')
    with pytest.raises(backup.BackupError, match='linked'):
        inspect(archive, tmp_path)
    (tmp_path / 'inspection').rmdir()
    archive = make_archive(journal, tmp_path)
    monkeypatch.setattr(backup, 'MAX_FILE_BYTES', 10)
    with pytest.raises(backup.BackupError, match='oversized'):
        inspect(archive, tmp_path)


def test_checksum_and_manifest_completeness(journal, tmp_path):
    archive = make_archive(journal, tmp_path)
    rewrite(archive, lambda contents: contents.__setitem__('uploads/note.txt', b'bad'))
    with pytest.raises(backup.BackupError, match='metadata|checksum'):
        inspect(archive, tmp_path)


@pytest.mark.parametrize('ddl', ['CREATE TABLE credentials(secret TEXT)', 'CREATE TABLE sqliteXcredentials(secret TEXT)', 'CREATE VIEW secret_view AS SELECT * FROM accounts', 'CREATE TRIGGER evil AFTER INSERT ON accounts BEGIN DELETE FROM trades; END'])
def test_unknown_tables_views_triggers_refused(journal, tmp_path, ddl):
    with closing(database.get_db()) as conn:
        conn.execute(ddl)
        conn.commit()
    with pytest.raises(backup.BackupError, match='schema'):
        make_archive(journal, tmp_path)


def test_foreign_key_breakage_refused(journal, tmp_path):
    with closing(sqlite3.connect(journal[0])) as conn:
        conn.execute('UPDATE trades SET account_id=999')
        conn.commit()
    with pytest.raises(backup.BackupError, match='foreign-key'):
        make_archive(journal, tmp_path)


def test_missing_attachments_preview_but_no_restore(journal, tmp_path):
    (journal[1] / 'note.txt').unlink()
    archive = make_archive(journal, tmp_path)
    assert inspect(archive, tmp_path)['missing_attachments'] == ['note.txt']
    with pytest.raises(backup.BackupError, match='missing diary'):
        backup.restore_archive(archive, *journal[:2], journal[2])
    assert not journal[2].exists()


def test_current_missing_attachment_prevents_unsafe_restore(journal, tmp_path):
    archive = make_archive(journal, tmp_path)
    (journal[1] / 'note.txt').unlink()
    with pytest.raises(backup.BackupError, match='current journal has missing'):
        backup.restore_archive(archive, *journal[:2], journal[2])
    assert not (journal[1] / 'note.txt').exists()


def test_failure_after_database_copy_rolls_back_both_stores(journal, tmp_path, monkeypatch):
    archive = make_archive(journal, tmp_path)
    with closing(database.get_db()) as conn:
        conn.execute("UPDATE accounts SET name='Keep me'")
        conn.commit()
    (journal[1] / 'note.txt').write_text('Keep attachment')
    original = backup._replace_database
    calls = []
    def fail_once(source, live):
        original(source, live)
        calls.append(source)
        if len(calls) == 1:
            raise OSError('Synthetic post-copy disk failure')
    monkeypatch.setattr(backup, '_replace_database', fail_once)
    with pytest.raises(backup.BackupError, match='previous journal was restored'):
        backup.restore_archive(archive, *journal[:2], journal[2])
    with closing(database.get_db()) as conn:
        assert conn.execute('SELECT name FROM accounts').fetchone()[0] == 'Keep me'
    assert (journal[1] / 'note.txt').read_text() == 'Keep attachment'
    assert len(backup.list_recovery(journal[2])['backups']) == 1


def test_routes_confirmation_local_guards_inspect_recovery(journal, tmp_path):
    app = FastAPI()
    app.include_router(backup_routes.create_router(lambda: journal[1], journal[2]))
    app.add_middleware(JournalMaintenanceMiddleware)
    client = TestClient(app, base_url='http://localhost', client=('127.0.0.1', 123))
    headers = {'X-Journal-Request': '1'}
    assert client.post('/api/backups/export').status_code == 403
    assert client.post('/api/backups/export', headers={**headers, 'Origin': 'https://evil.invalid'}).status_code == 403
    response = client.post('/api/backups/export', headers=headers)
    assert response.status_code == 200
    data = response.content
    assert client.post('/api/backups/inspect', headers=headers, files={'file': ('journal.zip', data)}).json()['counts']['trades'] == 1
    assert client.post('/api/backups/restore', headers=headers, files={'file': ('journal.zip', data)}, data={'confirmation': 'wrong'}).status_code == 400
    result = client.post('/api/backups/restore', headers=headers, files={'file': ('journal.zip', data)}, data={'confirmation': 'RESTORE'})
    assert result.status_code == 200, result.text
    identifier = result.json()['recovery_backup']['id']
    assert client.get('/api/backups/recovery').json()['backups'][0]['id'] == identifier
    assert client.get('/api/backups/recovery/' + identifier).status_code == 200
    remote = TestClient(app, base_url='http://localhost', client=('192.0.2.1', 123))
    assert remote.get('/api/backups/recovery').status_code == 403


def test_http_upload_limit_before_multipart_staging(journal, monkeypatch):
    app = FastAPI()
    app.include_router(backup_routes.create_router(lambda: journal[1], journal[2]))
    app.add_middleware(JournalMaintenanceMiddleware)
    client = TestClient(app, base_url='http://localhost', client=('127.0.0.1', 123))
    monkeypatch.setattr(journal_maintenance, 'MAX_ARCHIVE_BYTES', 1)
    response = client.post('/api/backups/inspect', headers={'X-Journal-Request': '1'}, files={'file': ('big.zip', b'x' * (1024 * 1024 + 100))})
    assert response.status_code == 413


def test_failed_rollback_halts_writes_but_preserves_recovery_download(journal, tmp_path, monkeypatch):
    archive = make_archive(journal, tmp_path)
    app = FastAPI()
    app.include_router(backup_routes.create_router(lambda: journal[1], journal[2]))
    @app.get('/api/ordinary')
    def ordinary():
        return {'ok': True}
    app.add_middleware(JournalMaintenanceMiddleware)
    client = TestClient(app, base_url='http://localhost', client=('127.0.0.1', 123))
    def broken(*args):
        raise OSError('Synthetic permanent failure')
    monkeypatch.setattr(backup, '_replace_database', broken)
    response = client.post('/api/backups/restore', headers={'X-Journal-Request': '1'}, files={'file': ('backup.zip', archive.read_bytes())}, data={'confirmation': 'RESTORE'})
    assert response.status_code == 503
    assert 'rollback could not finish' in response.json()['detail']
    assert client.get('/api/ordinary').status_code == 503
    recovery = client.get('/api/backups/recovery').json()['backups']
    assert len(recovery) == 1
    assert client.get('/api/backups/recovery/' + recovery[0]['id']).status_code == 200
    assert list(tmp_path.glob('.journal-restore-*/previous/note.txt'))


def test_duplicate_entry_and_manifest_inventory_rejected(journal, tmp_path):
    archive = make_archive(journal, tmp_path)
    with zipfile.ZipFile(archive, 'a') as contents:
        with pytest.warns(UserWarning):
            contents.writestr('uploads/note.txt', 'duplicate')
    with pytest.raises(backup.BackupError, match='duplicate'):
        inspect(archive, tmp_path)
    (tmp_path / 'inspection').rmdir()
    archive = make_archive(journal, tmp_path)
    rewrite(archive, lambda contents: contents.pop('uploads/note.txt'))
    with pytest.raises(backup.BackupError, match='manifest does not match'):
        inspect(archive, tmp_path)


def test_gate_drains_and_blocks_new_readers_until_restore_finishes():
    async def scenario():
        gate = JournalGate()
        events = []
        reader_release = asyncio.Event()
        writer_release = asyncio.Event()
        async def reader():
            async with gate.lease():
                events.append('existing request')
                await reader_release.wait()
                events.append('existing cleanup')
        async def writer():
            async with gate.lease(True):
                events.append('restore')
                await writer_release.wait()
        async def new_reader():
            async with gate.lease():
                events.append('new request')
        existing = asyncio.create_task(reader())
        await asyncio.sleep(0)
        restore = asyncio.create_task(writer())
        await asyncio.sleep(0)
        incoming = asyncio.create_task(new_reader())
        await asyncio.sleep(0)
        assert events == ['existing request']
        reader_release.set()
        await existing
        await asyncio.sleep(0)
        assert events == ['existing request', 'existing cleanup', 'restore']
        writer_release.set()
        await asyncio.gather(restore, incoming)
        assert events[-1] == 'new request'
        assert gate.readers == 0 and not gate.writer
    asyncio.run(scenario())


def test_middleware_keeps_lease_until_complete_asgi_lifecycle():
    async def scenario():
        events = []
        cleanup = asyncio.Event()
        async def app(scope, receive, send):
            events.append(scope['path'])
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'ok'})
            if scope['path'] == '/api/write':
                # Simulates dependency/background cleanup after response body.
                await cleanup.wait()
                events.append('cleanup')
        middleware = JournalMaintenanceMiddleware(app)
        async def noop(*args):
            pass
        base = {'type': 'http', 'method': 'POST', 'scheme': 'http', 'server': ('localhost', 80), 'client': ('127.0.0.1', 123), 'query_string': b'', 'headers': [(b'x-journal-request', b'1'), (b'host', b'localhost')]}
        first = asyncio.create_task(middleware({**base, 'path': '/api/write'}, noop, noop))
        await asyncio.sleep(0)
        second = asyncio.create_task(middleware({**base, 'path': '/api/backups/export'}, noop, noop))
        await asyncio.sleep(0)
        assert events == ['/api/write']
        cleanup.set()
        await asyncio.gather(first, second)
        assert events == ['/api/write', 'cleanup', '/api/backups/export']
    asyncio.run(scenario())
