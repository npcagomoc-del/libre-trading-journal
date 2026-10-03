import sqlite3
import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field, SecretStr
from database import get_db
from chatgpt_routes import require_local, require_mutation
import mt5_market_data as market
import mt5_mcp as mcp

class PrivateValidationRoute(APIRoute):
    """Validation errors can contain the raw body, even when the key is SecretStr."""
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def private_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={'detail':
                    'Check the MT5 broker, connection method, access key, symbol, and UTC offsets '
                    '(between -14 and +14), then try again.'})
        return private_handler


router = APIRouter(prefix='/api/market-data', route_class=PrivateValidationRoute)


def discard_key(config):
    try:
        mcp.remove_key(config)
    except (OSError, market.MarketDataError):
        logging.getLogger(__name__).warning('An obsolete encrypted MT5 credential could not be removed.')


def connection():
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def require_account(conn, account_id):
    if not conn.execute('SELECT id FROM accounts WHERE id=?', (account_id,)).fetchone():
        raise HTTPException(404, 'Journal account not found.')


class Connect(BaseModel):
    broker: Literal['exness', 'ftmo', 'fundednext']
    transport: Literal['terminal', 'mcp'] = 'terminal'
    path: str | None = None
    mcp_url: str = 'http://127.0.0.1:22346/mcp'
    mcp_api_key: SecretStr | None = None
    server_utc_offset_hours: float = Field(default=3, ge=-14, le=14, allow_inf_nan=False)
    utc_offset_hours: float = Field(default=0, ge=-14, le=14, allow_inf_nan=False)
    test_symbol: str = Field(default='XAUUSD', min_length=1, max_length=64)


@router.get('/{account_id}')
def status(account_id: int, request: Request, conn: sqlite3.Connection = Depends(connection)):
    require_local(request)
    require_account(conn, account_id)
    return {'config': market.public_config(market.load_config(conn, account_id)), 'installations': market.installations()}


@router.post('/{account_id}/connect')
def connect(account_id: int, body: Connect, request: Request, conn: sqlite3.Connection = Depends(connection)):
    require_mutation(request)
    require_account(conn, account_id)
    previous = market.load_config(conn, account_id)
    credential_id = None
    try:
        if body.transport == 'mcp':
            key = body.mcp_api_key.get_secret_value().strip() if body.mcp_api_key else ''
            if not key and previous and previous.get('mcp_url') == body.mcp_url:
                key = mcp.load_key(previous)
            config = mcp.connect(body.mcp_url, key, body.broker, body.utc_offset_hours, body.server_utc_offset_hours, body.test_symbol)
            credential_id = mcp.save_key(key)
            config['credential_id'] = credential_id
        else:
            config = market.connect(body.path or None, body.broker, body.utc_offset_hours, body.test_symbol)
        market.save_config(conn, account_id, config)
    except market.MarketDataError as error:
        if credential_id:
            discard_key({'credential_id': credential_id})
        raise HTTPException(400, str(error)) from None
    except Exception:
        if credential_id:
            discard_key({'credential_id':credential_id})
        raise HTTPException(500, 'MT5 connection could not be saved. Please retry.') from None
    if previous:
        discard_key(previous)
    return {'config': market.public_config(config), 'message': f"Connected to {body.broker.title()}. Retrieved {config['test_bars']} test candles for {config['test_symbol']}."}


@router.delete('/{account_id}')
def disconnect(account_id: int, request: Request, conn: sqlite3.Connection = Depends(connection)):
    require_mutation(request)
    require_account(conn, account_id)
    previous = market.load_config(conn, account_id)
    conn.execute('DELETE FROM settings WHERE account_id=? AND key=?', (account_id, market.SETTING_KEY))
    conn.commit()
    discard_key(previous)
    return {'disconnected': True}
