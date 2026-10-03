"""Single-process request exclusion for complete journal snapshots/restores.

The pure ASGI wrapper keeps leases until dependency cleanup, streamed responses,
and background tasks finish. Run one backend worker; external SQLite writers and
filesystem synchronization are outside this in-process coordination boundary.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

from chatgpt_routes import require_mutation
from journal_backup import MAX_ARCHIVE_BYTES


class JournalGate:
    def __init__(self):
        self.condition = asyncio.Condition()
        self.readers = 0
        self.writer = False
        self.waiting_writers = 0

    @asynccontextmanager
    async def lease(self, exclusive=False):
        async with self.condition:
            if exclusive:
                self.waiting_writers += 1
                try:
                    await self.condition.wait_for(lambda: not self.writer and not self.readers)
                    self.writer = True
                finally:
                    self.waiting_writers -= 1
                    self.condition.notify_all()
            else:
                await self.condition.wait_for(lambda: not self.writer and not self.waiting_writers)
                self.readers += 1
        try:
            yield
        finally:
            async with self.condition:
                if exclusive:
                    self.writer = False
                else:
                    self.readers -= 1
                self.condition.notify_all()


class JournalMaintenanceMiddleware:
    def __init__(self, app):
        self.app = app
        self.gate = JournalGate()
        self.recovery_required = False

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '').rstrip('/')
        if scope['type'] != 'http' or not (path == '/api' or path.startswith('/api/') or path == '/uploads' or path.startswith('/uploads/')):
            return await self.app(scope, receive, send)
        exclusive = scope['method'] == 'POST' and path in {'/api/backups/export', '/api/backups/restore'}
        backup_request = scope['method'] == 'POST' and path.startswith('/api/backups/')
        if backup_request:
            try:
                require_mutation(Request(scope))
            except HTTPException as exc:
                return await JSONResponse({'detail': exc.detail}, status_code=exc.status_code)(scope, receive, send)
        if backup_request:
            original_receive = receive
            received = 0
            async def bounded_receive():
                nonlocal received
                message = await original_receive()
                if message['type'] == 'http.request':
                    received += len(message.get('body', b''))
                    if received > MAX_ARCHIVE_BYTES + 1024 * 1024:
                        raise HTTPException(413, 'Backup upload exceeds the 512 MiB limit.')
                return message
            receive = bounded_receive
        async with self.gate.lease(exclusive):
            if self.recovery_required and not (scope['method'] == 'GET' and (path == '/api/backups/recovery' or path.startswith('/api/backups/recovery/'))):
                return await JSONResponse({'detail': 'Journal recovery is required. Download the recovery backup from Settings, stop the backend, and follow the recovery guide.'}, status_code=503)(scope, receive, send)
            scope['journal_maintenance_exclusive'] = exclusive
            try:
                await self.app(scope, receive, send)
            finally:
                if scope.get('journal_recovery_required'):
                    self.recovery_required = True
