import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mt5_mcp as mcp
import mt5_market_data as market
import database
from test_mt5_market_data import client

CONFIG = dict(transport='mcp', mcp_url='http://127.0.0.1:22346/mcp', broker='fundednext',
              login='12345678', server='FundedNext-Server 2', utc_offset_hours=0,
              server_utc_offset_hours=3, test_symbol='XAUUSD', test_bars=1)
ROW = dict(time='2026.10.02 14:50:00', open=4179.46, high=4183.0, low=4178.0,
           close=4182.2, tick_volume=42)


class Feed:
    def __init__(self, rows=None):
        self.rows = [ROW] if rows is None else rows
        self.calls = []
        self.login = CONFIG['login']

    def read(self, name, args=None):
        self.calls.append((name, args))
        if name == 'get_trading_account_info':
            return dict(account=dict(login=self.login, server=CONFIG['server'], broker='FundedNext Ltd'),
                        terminal=dict(server_connected=True))
        if name == 'get_marketwatch_symbols':
            return dict(symbols=[dict(symbol='XAUUSD', digits=2)])
        if name == 'get_chart_history':
            return dict(history=self.rows)
        raise AssertionError(name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_native_broker_clock_to_utc_and_exact_day_window():
    feed = Feed([ROW, ROW, {**ROW, 'time':'2026.10.02 02:55:00'},
                 {**ROW, 'time':'2026.10.03 03:00:00'}, {**ROW, 'open':float('nan')}])
    result = mcp.read_candles(feed, CONFIG, 'XAUUSD', '2026-10-02', '5Min', 1)
    args = next(args for name, args in feed.calls if name == 'get_chart_history')
    assert args['datetime_from'] == '2026-10-02T03:00:00'
    assert args['datetime_to'] == '2026-10-03T03:00:00'
    assert args['period'] == 'M5'
    assert result['bars'] == [dict(t='2026-10-02T11:50:00+00:00', o=4179.46, h=4183.0,
                                 l=4178.0, c=4182.2, v=42)]
    assert result['transport'] == 'mcp' and result['price_digits'] == 2
    assert result['feed_broker'] == 'fundednext' and result['volume_kind'] == 'ticks'


def test_trade_clock_and_aware_timestamps_do_not_double_shift():
    feed = Feed([{**ROW, 'time':'2026-10-01T22:30:00Z'}])
    result = mcp.read_candles(feed, CONFIG, 'XAUUSD', '2026-10-02', '5Min', 1, 2)
    assert result['bars'][0]['t'] == '2026-10-01T22:30:00+00:00'
    args = next(args for name, args in feed.calls if name == 'get_chart_history')
    assert args['datetime_from'] == '2026-10-02T01:00:00'
    assert result['utc_offset_hours'] == 2


def test_changed_account_and_empty_history_are_explicit():
    feed = Feed([])
    assert 'no candles' in mcp.read_candles(feed, CONFIG, 'XAUUSD', '2026-10-02', '5Min', 1)['warning']
    feed.login = '87654321'
    with pytest.raises(market.MarketDataError, match='different account'):
        mcp.read_candles(feed, CONFIG, 'XAUUSD', '2026-10-02', '5Min', 1)


@pytest.mark.parametrize('url', ['https://127.0.0.1:22346/mcp', 'http://example.com/mcp',
                               'http://127.0.0.1:22346/mcp?key=secret', 'http://user:secret@localhost/mcp',
                               'http://localhost:99999/mcp', 'http://localhost/other'])
def test_only_local_mcp_addresses_are_accepted(url):
    with pytest.raises(market.MarketDataError):
        mcp.local_url(url)


def test_mcp_protocol_session_sse_and_non_read_tools_blocked():
    requests = []
    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        assert request.headers['Authorization'] == 'Bearer test-key'
        if body['method'] == 'initialize':
            return httpx.Response(200, json={'result':{'protocolVersion':'2025-03-26'}}, headers={'Mcp-Session-Id':'test-session'})
        assert request.headers['Mcp-Session-Id'] == 'test-session'
        if body['method'] == 'notifications/initialized':
            return httpx.Response(202)
        result = {'jsonrpc':'2.0', 'id':body['id'], 'result':{'content':[{'type':'text','text':json.dumps({'history':[]})}]}}
        return httpx.Response(200, text='event: message\ndata: ' + json.dumps(result) + '\n\n', headers={'Content-Type':'text/event-stream'})
    connection = mcp.Client(CONFIG['mcp_url'], 'test-key')
    connection.http.close()
    connection.http = httpx.Client(transport=httpx.MockTransport(handle))
    with connection as connected:
        assert connected.read('get_chart_history') == {'history':[]}
        before = len(requests)
        for tool in ('place_order', 'execute_command', 'set_trading_account', 'symbol_select'):
            with pytest.raises(market.MarketDataError, match='read-only'):
                connected.read(tool)
        assert len(requests) == before


def test_rejected_key_is_not_echoed():
    connection = mcp.Client(CONFIG['mcp_url'], 'test-secret-key')
    connection.http.close()
    connection.http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401)))
    with pytest.raises(market.MarketDataError, match='rejected') as error:
        with connection:
            pass
    assert 'test-secret-key' not in str(error.value)


def test_encrypted_key_roundtrip_and_public_redaction(tmp_path, monkeypatch):
    pytest.importorskip('win32crypt')
    monkeypatch.setattr(mcp, 'vault_dir', lambda: tmp_path)
    credential_id = mcp.save_key('test-secret-key')
    config = {**CONFIG, 'credential_id':credential_id}
    assert b'test-secret-key' not in mcp.key_path(credential_id).read_bytes()
    assert mcp.load_key(config) == 'test-secret-key'
    public = market.public_config(config)
    assert public['has_key'] and public['account_label'].endswith('5678')
    assert 'credential_id' not in public and 'login' not in public
    mcp.remove_key(config)
    assert not mcp.key_path(credential_id).exists()


def test_mcp_route_saves_encrypted_reference_reuses_key_and_routes_charts(client, monkeypatch):
    calls = []
    removed = []
    def fake_client(url, key):
        if not key:
            raise market.MarketDataError('Enter the MT5 MCP access key.')
        return Feed()
    monkeypatch.setattr(mcp, 'Client', fake_client)
    original_connect = mcp.connect
    monkeypatch.setattr(mcp, 'connect', lambda *args: original_connect(*args, test_date='2026-10-02'))
    monkeypatch.setattr(mcp, 'save_key', lambda key: calls.append(('save', key)) or 'a'*32)
    monkeypatch.setattr(mcp, 'load_key', lambda config: 'test-key')
    monkeypatch.setattr(mcp, 'remove_key', lambda config: removed.append(config))
    headers = {'X-Journal-Request':'1', 'Origin':'http://localhost:3010'}
    payload = dict(transport='mcp', broker='fundednext', mcp_api_key='test-key')
    response = client.post('/api/market-data/1/connect', json=payload, headers=headers)
    assert response.status_code == 200
    public = response.json()['config']
    assert public['transport'] == 'mcp' and public['has_key']
    assert 'test-key' not in response.text and 'credential_id' not in public
    conn = database.get_db()
    saved = market.load_config(conn, 1)
    assert saved['credential_id'] == 'a'*32 and 'test-key' not in json.dumps(saved)
    conn.close()
    chart = client.get('/api/chart/XAUUSD/2026-10-02?instrument_type=GOLD&account_id=1&utc_offset_hours=0').json()
    assert chart['bars'][0]['t'] == '2026-10-02T11:50:00+00:00'
    assert chart['transport'] == 'mcp'
    assert client.get('/api/market-data/2').json()['config'] is None
    payload.pop('mcp_api_key')
    assert client.post('/api/market-data/1/connect', json=payload, headers=headers).status_code == 200
    assert calls == [('save','test-key'), ('save','test-key')]
    assert client.post('/api/market-data/1/connect', json={**payload, 'mcp_url':'http://localhost:2345/mcp'}, headers=headers).status_code == 400
    assert client.get('/api/market-data/1').json()['config']['mcp_url'] == CONFIG['mcp_url']
    assert client.delete('/api/market-data/1', headers=headers).status_code == 200
    assert client.get('/api/market-data/1').json()['config'] is None
