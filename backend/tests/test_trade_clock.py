import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trade_clock import entry_clock, philippine_performance


def trade(date='2026-10-02', time='11:53:00', pnl=10, source='exness', side='LONG'):
    return dict(date='2026-10-03', source=source, side=side, net_pnl=pnl,
                executions=[dict(date=date, time=time, action='SOLD' if side == 'SHORT' else 'BOT')])


def test_entry_date_short_and_overnight_are_not_closing_clock():
    record = trade(time='23:53:00', side='SHORT')
    record['executions'].insert(0, dict(date='2026-10-03', time='00:03:00', action='BOT'))
    original = copy.deepcopy(record)
    entry, status = entry_clock(record)
    assert status == 'ok'
    assert (entry['date'], entry['time']) == ('2026-10-03', '07:53')
    assert record == original


@pytest.mark.parametrize('date,time,session', [
    ('2026-10-02', '11:53', 'London'),
    ('2026-10-02', '12:30', 'London + New York'),
    ('2026-01-02', '12:30', 'London'),
    ('2026-01-02', '13:30', 'London + New York'),
    ('2026-10-02', '16:00', 'New York'),
    ('2026-10-03', '12:30', 'Outside sessions'),
    ('2026-10-02', '01:00', 'Sydney + Tokyo'),
])
def test_historical_sessions_and_boundaries(date, time, session):
    entry, _ = entry_clock(trade(date=date, time=time))
    assert entry['session'] == session


@pytest.mark.parametrize('clock,expected', [
    ('UTC', '19:53'), ('Asia/Manila', '11:53'),
    ('UTC+02:00', '17:53'), ('UTC+03:00', '16:53'),
    ('America/New_York', '23:53'), ('Europe/London', '18:53'),
])
def test_explicit_source_clocks(clock, expected):
    entry, _ = entry_clock(trade(source='generic'), clock)
    assert entry['time'] == expected


def test_unknown_source_and_explicit_metadata():
    record = trade(source='generic')
    assert entry_clock(record) == (None, 'unknown_clock')
    record['executions'][0]['timestamp_timezone'] = 'Asia/Manila'
    assert entry_clock(record)[0]['time'] == '11:53'
    record['executions'][0]['timestamp_timezone'] = 'invalid'
    assert entry_clock(record) == (None, 'unknown_clock')


def test_multiple_entries_use_earliest_instant_and_aware_offset():
    record = trade(time='16:00:00+00:00', source='generic')
    record['executions'].append(dict(date='2026-10-03', time='01:00:00+08:00', action='BOT'))
    entry, _ = entry_clock(record)
    assert (entry['date'], entry['time']) == ('2026-10-03', '00:00')


@pytest.mark.parametrize('date,time,clock,status', [
    ('2026-11-01', '01:30', 'America/New_York', 'ambiguous_timestamp'),
    ('2026-03-08', '02:30', 'America/New_York', 'ambiguous_timestamp'),
    ('2026-02-30', '10:00', 'UTC', 'invalid_timestamp'),
])
def test_refuse_invalid_and_ambiguous_local_times(date, time, clock, status):
    assert entry_clock(trade(date=date, time=time), clock) == (None, status)


def test_full_day_and_disjoint_sessions_reconcile_with_unknowns():
    records = [trade(time='12:30', pnl=20), trade(time='12:45', pnl=-5),
               trade(time='16:00', pnl=7), trade(source='generic', pnl=-2), trade(pnl=0)]
    result = philippine_performance(records)
    assert len(result['philippine_time_of_day']) == 48
    bucket = next(b for b in result['philippine_time_of_day'] if b['bucket'] == '20:30')
    assert bucket == dict(bucket='20:30', original_buckets=['12:30'],
                          original_clocks=[dict(source='Exness', timezone='UTC', label='UTC+0')],
                          original_entries=[dict(bucket='12:30', source='Exness', timezone='UTC', label='UTC+0')],
                          trade_count=2, net_pnl=15, win_rate=50, avg_pnl=7.5)
    assert result['time_conversion']['converted_count'] == 4
    assert result['time_conversion']['unconverted_count'] == 1
    assert sum(b['trade_count'] for b in result['trading_sessions']) == 5
    assert sum(b['net_pnl'] for b in result['trading_sessions']) == 20
    assert next(b for b in result['philippine_time_of_day'] if b['bucket'] == '00:00')['trade_count'] == 1


def test_missing_or_malformed_executions():
    assert entry_clock(dict(executions='bad')) == (None, 'invalid_timestamp')
    assert entry_clock(dict(executions=[])) == (None, 'missing_entry')
    assert entry_clock(dict(executions=[dict(action='BOT', time='10:00')])) == (None, 'missing_entry')


def test_paired_original_hours_keep_actual_source_clocks_and_rollover():
    utc = trade(time='16:10', pnl=7)
    local = trade(date='2026-10-03', time='00:20', pnl=-2, source='generic')
    local['executions'][0]['timestamp_timezone'] = 'Asia/Manila'
    entry, _ = entry_clock(utc)
    assert (entry['original_date'], entry['original_time']) == ('2026-10-02', '16:10')
    assert (entry['date'], entry['time']) == ('2026-10-03', '00:10')
    bucket = philippine_performance([utc, local])['philippine_time_of_day'][0]
    assert bucket['original_buckets'] == ['00:00', '16:00']
    assert (bucket['trade_count'], bucket['net_pnl']) == (2, 5)
    assert [clock['label'] for clock in bucket['original_clocks']] == ['Manila (UTC+8)', 'UTC+0']
    assert [(entry['bucket'], entry['label']) for entry in bucket['original_entries']] == [('00:00', 'Manila (UTC+8)'), ('16:00', 'UTC+0')]


def test_paired_original_hours_across_dst_dates_do_not_guess_one_offset():
    summer = trade(date='2026-07-01', time='11:10', pnl=3, source='generic')
    winter = trade(date='2026-01-02', time='10:10', pnl=4, source='generic')
    result = philippine_performance([summer, winter], 'America/New_York')
    bucket = next(b for b in result['philippine_time_of_day'] if b['bucket'] == '23:00')
    assert bucket['original_buckets'] == ['10:00', '11:00']
    assert (bucket['trade_count'], bucket['net_pnl']) == (2, 7)
    assert [clock['label'] for clock in bucket['original_clocks']] == ['New York (UTC-4)', 'New York (UTC-5)']


def test_exness_source_label_and_manual_clock_override_are_honest():
    entry, _ = entry_clock(trade())
    assert entry['original_clock'] == dict(source='Exness', timezone='UTC', label='UTC+0')
    overridden, _ = entry_clock(trade(), 'UTC+03:00')
    assert overridden['original_clock']['label'] == 'UTC+3'
    assert overridden['original_clock']['source'] == 'Exness'


def test_api_filters_conversion_and_persistence(tmp_path, monkeypatch):
    import database
    from fastapi.testclient import TestClient
    from main import app, get_connection
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'clock.db'))
    database.init_db()
    conn = database.get_db()
    conn.execute("INSERT INTO accounts(name,type) VALUES ('Clock test','day_trading')")
    conn.execute("INSERT INTO accounts(name,type) VALUES ('Other','day_trading')")
    record = trade(time='16:00')
    for account, date in [(1, '2026-10-03'), (1, '2026-10-04'), (2, '2026-10-03')]:
        conn.execute('INSERT INTO trades(account_id,trade_group,ticker,instrument_type,side,date,net_pnl,executions,source) VALUES(?,?,?,?,?,?,?,?,?)',
                     (account, f'test_{account}_{date}', 'XAUUSD', 'GOLD', 'LONG', date, 10, json.dumps(record['executions']), 'exness'))
    conn.commit()
    conn.close()
    def test_connection():
        connection = database.get_db()
        try:
            yield connection
        finally:
            connection.close()
    app.dependency_overrides[get_connection] = test_connection
    try:
        client = TestClient(app)
        params = dict(account_id=1, date_from='2026-10-03', date_to='2026-10-03')
        rows = client.get('/api/trades', params=params).json()
        assert len(rows) == 1
        assert rows[0]['entry_ph_time']['date'] == '2026-10-03'
        assert rows[0]['entry_ph_time']['time'] == '00:00'
        edge = client.get('/api/edge-report', params=params).json()
        assert edge['time_conversion']['converted_count'] == 1
        assert sum(b['trade_count'] for b in edge['trading_sessions']) == 1
        assert client.get('/api/trades', params={'source_timezone': 'bad'}).status_code == 422
        original = database.get_db()
        assert json.loads(original.execute('SELECT executions FROM trades LIMIT 1').fetchone()[0]) == record['executions']
        original.close()
    finally:
        app.dependency_overrides.pop(get_connection, None)
