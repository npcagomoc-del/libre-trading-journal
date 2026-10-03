"""Local-only backup endpoints; paths resolve dynamically for app/test isolation."""
import shutil
import sqlite3
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

import database
import journal_backup as backup
from chatgpt_routes import require_local, require_mutation


def mutation(request: Request):
    require_mutation(request)


def local(request: Request):
    require_local(request)


def _exclusive(request):
    if not request.scope.get('journal_maintenance_exclusive'):
        raise HTTPException(503, 'Journal maintenance coordination is unavailable; restart the backend.')


def _failure(exc):
    if isinstance(exc, backup.BackupError):
        raise HTTPException(400, str(exc)) from None
    raise HTTPException(500, 'The backup operation could not finish. Your recovery backups remain available; check free disk space and file permissions.') from exc


def _save_upload(file, target):
    size = 0
    with target.open('xb') as output:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > backup.MAX_ARCHIVE_BYTES:
                raise backup.BackupError('Backup file is too large (maximum 512 MiB).')
            output.write(chunk)


def create_router(upload_dir, recovery_dir=None):
    router = APIRouter(prefix='/api/backups')

    @router.post('/export', dependencies=[Depends(mutation)])
    def export(request: Request):
        _exclusive(request)
        folder = Path(tempfile.mkdtemp(prefix='journal-download-'))
        try:
            target = folder / 'libre-trading-journal.zip'
            manifest = backup.create_archive(database.DB_PATH, upload_dir(), target)
            return FileResponse(target, media_type='application/zip', filename=target.name,
                                headers={'Cache-Control': 'no-store', 'X-Journal-Missing-Attachments': str(len(manifest['missing_attachments']))},
                                background=BackgroundTask(shutil.rmtree, folder))
        except (backup.BackupError, OSError, sqlite3.Error) as exc:
            shutil.rmtree(folder)
            _failure(exc)

    @router.post('/inspect', dependencies=[Depends(mutation)])
    def inspect(file: UploadFile = File(...)):
        try:
            with tempfile.TemporaryDirectory(prefix='journal-upload-') as temp:
                root = Path(temp)
                target = root / 'uploaded.zip'
                _save_upload(file, target)
                staged = root / 'staged'
                staged.mkdir()
                manifest = backup.inspect_archive(target, staged)
                return {key: manifest[key] for key in ('format_version', 'created_at', 'counts', 'attachment_count', 'missing_attachments', 'warnings')}
        except (backup.BackupError, OSError, sqlite3.Error) as exc:
            _failure(exc)

    @router.post('/restore', dependencies=[Depends(mutation)])
    def restore(request: Request, file: UploadFile = File(...), confirmation: str = Form(...)):
        _exclusive(request)
        if confirmation != 'RESTORE':
            raise HTTPException(400, 'Type RESTORE to confirm replacing the entire journal.')
        try:
            with tempfile.TemporaryDirectory(prefix='journal-upload-') as temp:
                target = Path(temp) / 'uploaded.zip'
                _save_upload(file, target)
                return backup.restore_archive(target, database.DB_PATH, upload_dir(), recovery_dir)
        except backup.RecoveryRequired as exc:
            request.scope['journal_recovery_required'] = True
            raise HTTPException(503, str(exc)) from None
        except (backup.BackupError, OSError, sqlite3.Error) as exc:
            _failure(exc)

    @router.get('/recovery', dependencies=[Depends(local)])
    def recovery():
        return backup.list_recovery(recovery_dir)

    @router.get('/recovery/{identifier}', dependencies=[Depends(local)])
    def recovery_download(identifier: str):
        try:
            path = backup.recovery_path(identifier, recovery_dir)
        except backup.BackupError as exc:
            raise HTTPException(404, str(exc)) from None
        return FileResponse(path, media_type='application/zip', filename=path.name, headers={'Cache-Control': 'no-store'})

    return router
