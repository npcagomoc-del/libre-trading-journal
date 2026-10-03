import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import database
import mt5_market_data as market
import mt5_routes
import main


@pytest.fixture
def sdk(tmp_path, monkeypatch):
    path = tmp_path / 'terminal64.exe'
    path.touch()
    account = SimpleNamespace(login=12345678, server='FTMO-Demo', company='FTMO')
    symbol = SimpleNamespace(name='XAUUSD', digits=3)
    timestamp = int(datetime(2026, 10, 1, 22, 30, tzinfo=timezone.utc).timestamp())
    row = dict(time=timestamp, open=4100.123, high=4102.456, low=4100.1, close=4101.789, tick_volume=51)
    api = SimpleNamespace(TIMEFRAME_M5=5, TIMEFRAME_D1=1440, TIMEFRAME_W1=10080,
        initialize=lambda *a, **k: True, shutdown=lambda: None,
        terminal_info=lambda: SimpleNamespace(connected=True, path=str(tmp_path)),
        account_info=lambda: account, symbols_get=lambda: (symbol,), symbol_select=lambda *a: True,
        copy_rates_from_pos=lambda *a: [row], copy_rates_range=lambda *a: [row])
    monkeypatch.setattr(market.importlib, 'import_module', lambda name: api)
    config = dict(path=str(path), broker='ftmo', login=str(account.login), server=account.server,
                  utc_offset_hours=2, test_symbol='XAUUSD', test_bars=1)
    return api, config, row


def test_utc_window_precision_tick_volume_dedup_and_filter(sdk):
    api, config, row = sdk
    seen = []
    def rates(symbol, timeframe, start, end):
        seen.append((symbol, timeframe, start, end))
        return [row, {**row, 'time': row['time'] - 86400}, row, {**row, 'open': float('nan')}]
    api.copy_rates_range = rates
    result = market.candles(config, 'XAUUSD', '2026-10-02', '5Min', 1)
    assert seen[0][2].isoformat() == '2026-10-01T22:00:00+00:00'
    assert seen[0][3].isoformat() == '2026-10-02T21:59:59.999999+00:00'
    assert result['bars'] == [dict(t='2026-10-01T22:30:00+00:00', o=4100.123, h=4102.456, l=4100.1, c=4101.789, v=51)]
    assert result['price_digits'] == 3
    assert result['volume_kind'] == 'ticks'


def test_exness_trade_clock_overrides_ftmo_feed_clock(sdk):
    api, config, row = sdk
    assert market.candles(config, 'XAUUSD', '2026-10-01', '5Min', 1, 0)['bars']
    assert not market.candles(config, 'XAUUSD', '2026-10-02', '5Min', 1, 0)['bars']
    # True UTC timestamps are retained; the frontend displays the chosen clock.
    result = market.candles(config, 'XAUUSD', '2026-10-02', '1Day', 2, 0)
    assert result['utc_offset_hours'] == 0 and result['bars'][0]['t'].endswith('+00:00')


def test_changed_terminal_account_and_provider_cannot_silently_supply_prices(sdk):
    api, config, _ = sdk
    api.account_info = lambda: SimpleNamespace(login=87654321, server='FTMO-Demo', company='FTMO')
    with pytest.raises(market.MarketDataError, match='different account'):
        market.candles(config, 'XAUUSD', '2026-10-02', '5Min', 1)
    with pytest.raises(market.MarketDataError, match='does not match Exness'):
        market.connect(config['path'], 'exness', 0)


def test_broker_suffix_mapping_and_ambiguity(sdk):
    api, _, _ = sdk
    assert market.resolve_symbol(api, 'XAUUSDm').name == 'XAUUSD'
    api.symbols_get = lambda: [SimpleNamespace(name='XAUUSDm'), SimpleNamespace(name='XAUUSDc')]
    with pytest.raises(market.MarketDataError, match='Several MT5 symbols'):
        market.resolve_symbol(api, 'XAUUSD')
    assert market.resolve_symbol(api, 'xauusdm').name == 'XAUUSDm'
    with pytest.raises(market.MarketDataError, match='unavailable'):
        market.resolve_symbol(api, 'UNKNOWNSUFFIX')


def test_disconnected_terminal_and_missing_history_fail_clearly(sdk):
    api, config, _ = sdk
    api.terminal_info = lambda: SimpleNamespace(connected=False)
    with pytest.raises(market.MarketDataError, match='not connected'):
        market.connect(config['path'], 'ftmo', 0)
    api.terminal_info = lambda: SimpleNamespace(connected=True)
    api.copy_rates_from_pos = lambda *a: []
    with pytest.raises(market.MarketDataError, match='No candles'):
        market.connect(config['path'], 'ftmo', 0)
    api.copy_rates_range = lambda *a: None
    with pytest.raises(market.MarketDataError, match='retrieve history'):
        market.candles(config, 'XAUUSD', '2026-10-02', '5Min', 1)


def test_shutdown_runs_after_account_validation_failure(sdk):
    api, config, _ = sdk
    closed = []
    api.shutdown = lambda: closed.append(True)
    api.account_info = lambda: None
    with pytest.raises(market.MarketDataError):
        market.connect(config['path'], 'ftmo', 0)
    assert closed == [True]


def test_authorization_failure_gives_mt5_login_instructions(sdk):
    api, config, _ = sdk
    api.initialize = lambda *a, **k: False
    api.last_error = lambda: (-6, 'Terminal: Authorization failed')
    with pytest.raises(market.MarketDataError, match='Login to Trade Account'):
        market.connect(config['path'], 'ftmo', 0)


@pytest.mark.parametrize('offset', [float('nan'), float('inf'), -15, 15])
def test_invalid_clock(sdk, offset):
    _, config, _ = sdk
    with pytest.raises(market.MarketDataError, match='UTC offset'):
        market.candles(config, 'XAUUSD', '2026-10-02', '5Min', 1, offset)


def test_connect_uses_saved_session_and_redacts_account_number(sdk):
    api, config, _ = sdk
    calls = []
    api.initialize = lambda *a, **k: calls.append((a, k)) or True
    saved = market.connect(config['path'], 'ftmo', 0)
    assert calls == [((config['path'],), {'timeout': 10000})]
    public = market.public_config(saved)
    assert 'login' not in public and public['account_label'] == 'Account ending 5678'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'test.db'))
    database.init_db()
    conn = database.get_db()
    conn.execute("INSERT INTO accounts(name,type) VALUES('Exness journal','day_trading')")
    conn.execute("INSERT INTO accounts(name,type) VALUES('FTMO journal','day_trading')")
    conn.commit(); conn.close()
    app = FastAPI()
    app.include_router(mt5_routes.router)
    app.add_api_route('/api/chart/{ticker}/{date}', main.get_chart, methods=['GET'])
    return TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000))


@pytest.mark.parametrize('payload', [
    {'mcp_api_key': 'synthetic-validation-secret'},
    {'broker': 'synthetic-validation-secret', 'mcp_api_key': 'synthetic-validation-secret'},
    {'broker': 'ftmo', 'mcp_api_key': {'key': 'synthetic-validation-secret'}},
    {'broker': 'ftmo', 'mcp_api_key': 'synthetic-validation-secret', 'utc_offset_hours': 15},
])
def test_invalid_connection_never_echoes_submitted_key(client, monkeypatch, payload):
    def unexpected(*args, **kwargs):
        pytest.fail('Invalid settings must not reach a terminal, network, or credential store')
    monkeypatch.setattr(market, 'connect', unexpected)
    monkeypatch.setattr(mt5_routes.mcp, 'connect', unexpected)
    monkeypatch.setattr(mt5_routes.mcp, 'save_key', unexpected)
    monkeypatch.setattr(mt5_routes.mcp, 'load_key', unexpected)
    response = client.post('/api/market-data/1/connect', json=payload,
                           headers={'X-Journal-Request': '1', 'Origin': 'http://localhost:3010'})
    assert response.status_code == 422
    assert isinstance(response.json()['detail'], str)
    assert 'Check the MT5' in response.json()['detail']
    assert 'synthetic-validation-secret' not in response.text
    assert 'mcp_api_key' not in response.text


def test_account_scoped_routes_guards_disconnect_and_chart_routing(client, sdk):
    _, config, _ = sdk
    payload = {'path': config['path'], 'broker': 'ftmo', 'utc_offset_hours': 0}
    url = '/api/market-data/1'
    headers = {'X-Journal-Request': '1', 'Origin': 'http://localhost:3010'}
    assert client.post(url + '/connect', json=payload).status_code == 403
    assert client.post(url + '/connect', json=payload, headers={**headers, 'Origin':'https://example.com'}).status_code == 403
    assert client.post(url + '/connect', json={**payload, 'utc_offset_hours': 15}, headers=headers).status_code == 422
    assert client.post('/api/market-data/999/connect', json=payload, headers=headers).status_code == 404
    response = client.post(url + '/connect', json=payload, headers=headers)
    assert response.status_code == 200 and 'login' not in response.json()['config']
    assert client.get('/api/market-data/2').json()['config'] is None
    chart = '/api/chart/XAUUSD/2026-10-01?instrument_type=GOLD&account_id=1'
    assert client.get(chart).json()['provider'] == 'mt5'
    assert client.get(chart, headers={'Origin':'https://example.com'}).status_code == 403
    assert client.get(chart.replace('account_id=1', 'account_id=2')).json()['bars'] == []
    assert client.delete(url, headers=headers).status_code == 200
    assert client.get(url).json()['config'] is None
    conn = database.get_db()
    assert conn.execute('SELECT COUNT(*) FROM accounts').fetchone()[0] == 2
    conn.close()
