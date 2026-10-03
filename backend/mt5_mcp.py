"""Local, read-only MT5 MCP client. The server cannot select arbitrary tools."""
import json
import math
import os
import re
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from mt5_market_data import MarketDataError, TIMEFRAMES

READ_TOOLS = frozenset({'get_chart_history', 'get_trading_account_info',
                        'get_time_information', 'get_marketwatch_symbols'})


def local_url(url):
    try:
        parsed = urlsplit(url)
        valid_port = parsed.port is None or 1 <= parsed.port <= 65535
    except ValueError:
        raise MarketDataError('Use the local MT5 MCP address, for example http://127.0.0.1:22346/mcp.') from None
    if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
            or parsed.username or parsed.password or parsed.query or parsed.fragment or not valid_port
            or parsed.path != '/mcp'):
        raise MarketDataError('MT5 MCP must use a localhost HTTP address ending in /mcp.')
    return url


def decode(response):
    try:
        return response.json()
    except ValueError:
        for chunk in response.text.replace('\r\n', '\n').split('\n\n'):
            data = '\n'.join(line[5:].strip() for line in chunk.splitlines() if line.startswith('data:'))
            if data:
                try:
                    item = json.loads(data)
                except ValueError:
                    continue
                if 'result' in item or 'error' in item:
                    return item
        raise MarketDataError('MT5 MCP returned an unreadable response.') from None


class Client:
    def __init__(self, url, key):
        self.url = local_url(url)
        if not key or len(key) > 512 or '\n' in key or '\r' in key:
            raise MarketDataError('Enter the MT5 MCP access key from Tools → Options → MCP.')
        self.headers = {'Authorization':'Bearer ' + key, 'Accept':'application/json, text/event-stream'}
        self.http = httpx.Client(timeout=20, follow_redirects=False, trust_env=False)
        self.counter = 0

    def _post(self, body):
        try:
            response = self.http.post(self.url, headers=self.headers, json=body)
        except httpx.HTTPError:
            raise MarketDataError('Cannot reach MT5 MCP. Keep the terminal open and enable its internal MCP server.') from None
        if response.status_code in {401, 403}:
            raise MarketDataError('MT5 MCP rejected the access key or permission. Check the key in Tools → Options → MCP.')
        if response.status_code not in {200, 202, 204}:
            raise MarketDataError('MT5 MCP could not complete this read request. Check the terminal and try again.')
        return response

    def _rpc(self, method, params):
        self.counter += 1
        response = self._post({'jsonrpc':'2.0', 'id':self.counter, 'method':method, 'params':params})
        if len(response.content) > 8_000_000:
            raise MarketDataError('Too much MT5 history was returned. Choose a shorter chart period.')
        data = decode(response)
        if 'error' in data or 'result' not in data:
            raise MarketDataError('MT5 MCP could not read the requested data. Check the symbol, history and terminal permissions.')
        return data['result'], response

    def __enter__(self):
        try:
            result, response = self._rpc('initialize', {'protocolVersion':'2025-03-26', 'capabilities':{},
                'clientInfo':{'name':'trading-journal-readonly-charts', 'version':'1.0'}})
            if response.headers.get('Mcp-Session-Id'):
                self.headers['Mcp-Session-Id'] = response.headers['Mcp-Session-Id']
            self.headers['MCP-Protocol-Version'] = result.get('protocolVersion', '2025-03-26')
            self._post({'jsonrpc':'2.0', 'method':'notifications/initialized'})
            return self
        except Exception:
            self.http.close()
            raise

    def __exit__(self, *args):
        self.http.close()

    def read(self, name, arguments=None):
        if name not in READ_TOOLS:
            raise MarketDataError('This journal connection only permits read-only chart and account tools.')
        result, _ = self._rpc('tools/call', {'name':name, 'arguments':arguments or {}})
        if result.get('isError'):
            raise MarketDataError('MT5 MCP could not read this data. Check the selected symbol and available history in MT5.')
        if isinstance(result.get('structuredContent'), dict):
            return result['structuredContent']
        for content in result.get('content', []):
            if content.get('type') == 'text':
                try:
                    return json.loads(content.get('text', ''))
                except ValueError:
                    continue
        raise MarketDataError('MT5 MCP returned an unsupported data format.')


def vault_dir():
    if os.name != 'nt':
        raise MarketDataError('Encrypted MT5 MCP credentials currently require Windows.')
    return Path(os.environ['LOCALAPPDATA']) / 'TradingJournalAI' / 'mt5-mcp'


def key_path(credential_id):
    if not re.fullmatch(r'[0-9a-f]{32}', credential_id or ''):
        raise MarketDataError('Reconnect MT5 MCP from Settings to save its access key.')
    return vault_dir() / (credential_id + '.bin')


def save_key(key):
    import win32crypt
    directory = vault_dir()
    directory.mkdir(parents=True, exist_ok=True)
    credential_id = uuid.uuid4().hex
    blob = win32crypt.CryptProtectData(key.encode('utf-8'), 'Trading Journal MT5 MCP', None, None, None, 1)
    fd, temporary = tempfile.mkstemp(dir=directory, prefix='mcp-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as file:
            file.write(blob)
        os.replace(temporary, key_path(credential_id))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return credential_id


def load_key(config):
    import win32crypt
    try:
        return win32crypt.CryptUnprotectData(key_path(config.get('credential_id')).read_bytes(), None, None, None, 1)[1].decode('utf-8')
    except Exception:
        raise MarketDataError('The saved MT5 MCP access key could not be opened. Reconnect in Settings.') from None


def remove_key(config):
    if config and config.get('credential_id'):
        key_path(config['credential_id']).unlink(missing_ok=True)


def account_identity(client, expected=None):
    data = client.read('get_trading_account_info')
    account = data.get('account') or {}
    if not data.get('terminal', {}).get('server_connected') or not account.get('login') or not account.get('server'):
        raise MarketDataError('The MT5 MCP terminal is not signed into a connected trading account.')
    identity = {'login':str(account['login']), 'server':str(account['server']), 'company':str(account.get('broker', ''))}
    if expected and any(identity[k] != expected[k] for k in ('login', 'server')):
        raise MarketDataError('MT5 MCP is signed into a different account. Restore the saved account or reconnect this journal account in Settings.')
    return identity


def symbol_info(client, ticker):
    symbols = client.read('get_marketwatch_symbols', {'symbol':ticker, 'include_hidden':True, 'limit':1000}).get('symbols', [])
    if not symbols:
        # Cross-broker reference feeds can remove a suffix from recognised pairs.
        base = ticker[:6].upper()
        codes = {'USD','EUR','GBP','JPY','AUD','NZD','CAD','CHF','SGD','HKD','ZAR','XAU','XAG','BTC','ETH'}
        if len(ticker) > 6 and base[:3] in codes and base[3:] in codes:
            symbols = client.read('get_marketwatch_symbols', {'symbol':base, 'include_hidden':True, 'limit':1000}).get('symbols', [])
        elif len(ticker) == 6:
            all_symbols = client.read('get_marketwatch_symbols', {'include_hidden':True, 'limit':1000}).get('symbols', [])
            symbols = [s for s in all_symbols if s.get('symbol', '').upper().startswith(ticker.upper())]
    if len(symbols) != 1:
        if symbols:
            raise MarketDataError('Several MT5 symbols match. Enter the exact Market Watch symbol in the trade.')
        raise MarketDataError(f'{ticker} is unavailable on the connected MT5 MCP account. Check Market Watch.')
    return symbols[0]


def server_datetime(value):
    # Native MCP emits the same naive broker-clock timestamps shown in MT5.
    try:
        return datetime.strptime(value, '%Y.%m.%d %H:%M:%S')
    except (ValueError, TypeError):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, TypeError, AttributeError):
            raise MarketDataError('MT5 MCP returned an invalid candle timestamp.') from None
        return parsed


def read_candles(client, config, ticker, date, timeframe, days_back, offset=None):
    if timeframe not in TIMEFRAMES:
        raise MarketDataError('Unsupported chart timeframe.')
    offset = config['utc_offset_hours'] if offset is None else offset
    server_offset = config['server_utc_offset_hours']
    if not all(math.isfinite(v) and -14 <= v <= 14 for v in (offset, server_offset)):
        raise MarketDataError('Chart clock offsets must be between -14 and +14 hours.')
    day = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    cap = 5475 if timeframe == '1Week' else 3650 if timeframe == '1Day' else 90
    days_back = max(1, min(days_back, cap))
    start = day - timedelta(days=days_back - 1, hours=offset)
    end = day + timedelta(days=1, hours=-offset)
    symbol = symbol_info(client, ticker)
    args = {'symbol':symbol['symbol'], 'period':TIMEFRAMES[timeframe],
            'datetime_from':(start + timedelta(hours=server_offset)).replace(tzinfo=None).isoformat(),
            'datetime_to':(end + timedelta(hours=server_offset)).replace(tzinfo=None).isoformat(), 'limit':20000}
    result = client.read('get_chart_history', args)
    rows = result.get('history')
    if not isinstance(rows, list):
        raise MarketDataError('MT5 MCP returned no supported candle history.')
    bars = []
    for row in rows:
        timestamp = server_datetime(row['time'])
        utc = timestamp.astimezone(timezone.utc) if timestamp.tzinfo else (timestamp - timedelta(hours=server_offset)).replace(tzinfo=timezone.utc)
        if not start <= utc < end:
            continue
        try:
            prices = [float(row[k]) for k in ('open','high','low','close')]
            volume = max(0, int(row.get('tick_volume', 0)))
        except (KeyError, ValueError, TypeError):
            continue
        if not all(math.isfinite(p) and p > 0 for p in prices) or not prices[2] <= min(prices[0],prices[3]) <= max(prices[0],prices[3]) <= prices[1]:
            continue
        bars.append(dict(t=utc.isoformat(), o=prices[0], h=prices[1], l=prices[2], c=prices[3], v=volume))
    bars = sorted({b['t']:b for b in bars}.values(), key=lambda b:b['t'])
    account_identity(client, config)
    warning = None if bars else 'MT5 MCP has no candles for this period. Open this symbol and timeframe in MT5 to load history.'
    if bars and len(rows) >= 20000:
        warning = 'MT5 history reached the request limit. Choose a shorter period for complete coverage.'
    return {'ticker':ticker, 'date':date, 'bars':bars, 'provider':'mt5', 'transport':'mcp',
            'feed_broker':config['broker'], 'resolved_symbol':symbol['symbol'],
            'utc_offset_hours':offset, 'server_utc_offset_hours':server_offset,
            'price_digits':max(0, min(10, int(symbol['digits']))), 'volume_kind':'ticks', 'warning':warning}


def connect(url, key, broker, offset, server_offset, ticker, test_date=None):
    with Client(url, key) as client:
        identity = account_identity(client)
        if broker not in (identity['server'] + ' ' + identity['company']).lower():
            raise MarketDataError(f'The MCP terminal does not match {broker.title()}. Select its actual price provider.')
        config = {'transport':'mcp', 'mcp_url':local_url(url), 'broker':broker,
                  'login':identity['login'], 'server':identity['server'],
                  'utc_offset_hours':offset, 'server_utc_offset_hours':server_offset, 'test_symbol':ticker}
        date = test_date or datetime.now(timezone.utc).strftime('%Y-%m-%d')
        result = read_candles(client, config, ticker, date, '5Min', 7)
        if not result['bars']:
            raise MarketDataError('MT5 MCP returned no test candles. Open this symbol in MT5 to load its history, then retry.')
        config.update(test_symbol=result['resolved_symbol'], test_bars=len(result['bars']))
        return config


def candles(config, ticker, date, timeframe, days_back, offset=None):
    with Client(config['mcp_url'], load_key(config)) as client:
        account_identity(client, config)
        return read_candles(client, config, ticker, date, timeframe, days_back, offset)
