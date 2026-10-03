"""Read-only candles from an existing local MT5 session. No trading API calls."""
import importlib
import json
import math
import os
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOCK = threading.RLock()
TIMEFRAMES = {'1Min': 'M1', '3Min': 'M3', '5Min': 'M5', '10Min': 'M10',
              '15Min': 'M15', '30Min': 'M30', '1Hour': 'H1', '1Day': 'D1', '1Week': 'W1'}
SETTING_KEY = 'mt5_market_data'


class MarketDataError(ValueError):
    pass


def installations():
    found = set()
    for root in (os.environ.get('ProgramFiles', 'C:/Program Files'), os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')):
        folder = Path(root)
        if folder.exists():
            for item in folder.iterdir():
                if item.is_dir() and any(word in item.name.lower() for word in ('metatrader', 'mt5', 'exness', 'ftmo')):
                    terminal = item / 'terminal64.exe'
                    if terminal.is_file():
                        found.add(str(terminal))
    # Prefer the generic terminal over installations branded for other brokers.
    return sorted(found, key=lambda p: (Path(p).parent.name.lower() != 'metatrader 5', p.lower()))


def load_config(conn, account_id):
    row = conn.execute('SELECT value FROM settings WHERE account_id=? AND key=?', (account_id, SETTING_KEY)).fetchone()
    return json.loads(row[0]) if row else None


def save_config(conn, account_id, config):
    conn.execute('INSERT INTO settings(account_id,key,value) VALUES(?,?,?) ON CONFLICT(account_id,key) DO UPDATE SET value=excluded.value',
                 (account_id, SETTING_KEY, json.dumps(config)))
    conn.commit()


@contextmanager
def session(path=None, expected=None):
    try:
        api = importlib.import_module('MetaTrader5')
    except ImportError:
        raise MarketDataError('MT5 support is not installed in this backend. Install its requirements and restart the journal.') from None
    if path and (Path(path).name.lower() != 'terminal64.exe' or not Path(path).is_file()):
        raise MarketDataError('Select the terminal64.exe from your MT5 installation.')
    with LOCK:
        try:
            ok = api.initialize(path, timeout=10000) if path else api.initialize(timeout=10000)
            if not ok:
                error = api.last_error()
                if error and error[0] == -6:
                    raise MarketDataError('MT5 sign-in failed. In MT5, use File → Login to Trade Account with your FTMO or Exness login and exact server, then reconnect.')
                raise MarketDataError('Open MT5 and sign into your Exness or FTMO account, then try Connect again.')
            terminal = api.terminal_info()
            account = api.account_info()
            if not terminal or not terminal.connected or not account:
                raise MarketDataError('MT5 is not connected to a trading server. Sign into MT5 first.')
            identity = {'login': str(account.login), 'server': account.server}
            if expected and any(identity[k] != expected[k] for k in ('login', 'server')):
                raise MarketDataError('MT5 is signed into a different account. Restore the saved account in MT5, or reconnect this journal account in Settings.')
            yield api, account, terminal
        except MarketDataError:
            raise
        except Exception:
            raise MarketDataError('MT5 could not read this price feed. Check the terminal connection and symbol, then retry.') from None
        finally:
            api.shutdown()


def resolve_symbol(api, ticker):
    symbols = api.symbols_get() or ()
    exact = [s for s in symbols if s.name.upper() == ticker.upper()]
    candidates = exact or [s for s in symbols if s.name.upper().startswith(ticker.upper())]
    # A trade can carry an Exness suffix while the selected reference feed is
    # FTMO. Only recognised currency/metals/crypto pairs allow suffix removal.
    base = ticker.upper()[:6]
    known_codes = {'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF', 'SGD', 'HKD', 'ZAR', 'XAU', 'XAG', 'BTC', 'ETH'}
    if not candidates and len(ticker) > 6 and base[:3] in known_codes and base[3:] in known_codes and re.fullmatch(r'[A-Za-z0-9._-]+', ticker):
        candidates = [s for s in symbols if s.name.upper() == base]
        if not candidates:
            candidates = [s for s in symbols if s.name.upper().startswith(base)]
    if len(candidates) != 1:
        if candidates:
            raise MarketDataError('Several MT5 symbols match. Use the exact broker symbol in your trade: ' + ', '.join(s.name for s in candidates[:8]))
        raise MarketDataError(f'{ticker} is unavailable on this MT5 account. Check the exact name in MT5 Market Watch.')
    symbol = candidates[0]
    if not api.symbol_select(symbol.name, True):
        raise MarketDataError('MT5 could not enable this symbol in Market Watch.')
    return symbol


def connect(path, broker, offset, ticker='XAUUSD'):
    with session(path) as (api, account, terminal):
        text = (account.server + ' ' + account.company).lower()
        if broker.lower() not in text:
            raise MarketDataError(f'The connected MT5 server does not match {broker.title()}. Sign into the intended account in MT5 or choose the matching provider.')
        symbol = resolve_symbol(api, ticker)
        # Closed markets still have historical bars: a recent-history test is
        # preferable to requiring a live tick on weekends.
        rows = api.copy_rates_from_pos(symbol.name, api.TIMEFRAME_M5, 0, 10)
        if rows is None or len(rows) == 0:
            raise MarketDataError(f'No candles returned for {symbol.name}. Open its 5-minute chart in MT5 to download history, then retry.')
        path = path or str(Path(terminal.path) / 'terminal64.exe')
        return {'path': path, 'broker': broker, 'login': str(account.login), 'server': account.server,
                'utc_offset_hours': offset, 'test_symbol': symbol.name, 'test_bars': len(rows)}


def public_config(config):
    if not config:
        return None
    return {**{k: v for k, v in config.items() if k not in {'login', 'credential_id', 'api_key'}},
            'account_label': 'Account ending ' + config['login'][-4:], 'has_key':bool(config.get('credential_id'))}


def candles(config, ticker, date, timeframe, days_back, offset=None):
    if config.get('transport') == 'mcp':
        from mt5_mcp import candles as mcp_candles
        return mcp_candles(config, ticker, date, timeframe, days_back, offset)
    if timeframe not in TIMEFRAMES:
        raise MarketDataError('Unsupported chart timeframe.')
    offset = config['utc_offset_hours'] if offset is None else offset
    if not math.isfinite(offset) or not -14 <= offset <= 14:
        raise MarketDataError('Trade clock UTC offset must be between -14 and +14 hours.')
    day = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    cap = 5475 if timeframe == '1Week' else 3650 if timeframe == '1Day' else 90
    days_back = max(1, min(days_back, cap))
    start = day - timedelta(days=days_back - 1, hours=offset)
    end = day + timedelta(days=1, hours=-offset) - timedelta(microseconds=1)
    with session(config['path'], config) as (api, _, _):
        symbol = resolve_symbol(api, ticker)
        rows = api.copy_rates_range(symbol.name, getattr(api, 'TIMEFRAME_' + TIMEFRAMES[timeframe]), start, end)
        if rows is None:
            raise MarketDataError('MT5 could not retrieve history. Open this symbol and timeframe in MT5, wait for history to load, then retry.')
        bars = []
        for row in rows:
            t = int(row['time'])
            if not start.timestamp() <= t <= end.timestamp():
                continue
            prices = [float(row[k]) for k in ('open', 'high', 'low', 'close')]
            if not all(math.isfinite(v) and v > 0 for v in prices):
                continue
            bars.append({'t': datetime.fromtimestamp(t, timezone.utc).isoformat(),
                         'o': prices[0], 'h': prices[1], 'l': prices[2], 'c': prices[3],
                         'v': int(row['tick_volume'])})
        bars = sorted({b['t']: b for b in bars}.values(), key=lambda b: b['t'])
        return {'ticker': ticker, 'date': date, 'bars': bars, 'provider': 'mt5',
                'feed_broker': config['broker'], 'resolved_symbol': symbol.name,
                'utc_offset_hours': offset, 'price_digits': symbol.digits,
                'volume_kind': 'ticks', 'warning': None if bars else 'MT5 has no candles for this period. Check trading hours or load more history in MT5.'}
