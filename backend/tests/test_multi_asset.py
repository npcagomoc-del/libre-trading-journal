import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import database
from csv_parser import parse_broker_csv, parse_trade_history_section
from main import TradeCreate, create_trade, add_execution, update_execution


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'test.db'))
    database.init_db()
    conn = database.get_db()
    conn.execute("INSERT INTO accounts (name,type) VALUES ('Test','day_trading')")
    conn.commit()
    yield conn
    conn.close()


@pytest.mark.parametrize('asset,ticker,qty,entry,exit_price,multiplier,expected', [
    ('CRYPTO', 'BTCUSD', .001, 60000, 61000, 1, 1),
    ('FOREX', 'EURUSD', .1, 1.1, 1.102, 100000, 20),
    ('GOLD', 'XAUUSD', .1, 2300, 2310, 100, 100),
    ('OPTION', 'SPY', 2, 3, 4, 100, 200),
    ('FUTURE', '/MES', 1, 6000, 6001, 5, 5),
])
def test_create_and_execution_edit_preserve_sizing(db, asset, ticker, qty, entry, exit_price, multiplier, expected):
    trade = create_trade(TradeCreate(account_id=1, date='2026-10-02', ticker=ticker,
        instrument_type=asset, side='LONG', quantity=qty, entry_price=entry,
        exit_price=exit_price, multiplier=multiplier, commissions=.2), db)
    assert trade['gross_pnl'] == pytest.approx(expected)
    assert trade['net_pnl'] == pytest.approx(expected - .2)
    fills = json.loads(trade['executions'])
    assert fills[0]['qty'] == qty
    fills[1]['price'] = exit_price
    # UI edits need not resend sizing: the stored execution supplies it.
    fills[1].pop('multiplier')
    updated = update_execution(trade['id'], 1, fills[1], db)
    assert updated['net_pnl'] == trade['net_pnl']
    assert json.loads(updated['executions'])[1]['multiplier'] == multiplier


def test_fractional_short_forex_closes_and_converts(db):
    trade = create_trade(TradeCreate(account_id=1, date='2026-10-02', ticker='USDJPY',
        instrument_type='FOREX', side='SHORT', quantity=.1, multiplier=100000,
        entry_price=150, quote_currency='JPY', quote_to_usd_rate=.0067), db)
    updated = add_execution(trade['id'], {'action':'BOT','qty':.1,'price':149,'commission':1}, db)
    assert updated['gross_pnl'] == 67
    assert updated['net_pnl'] == 66


def test_generic_import_fractional_asset_and_currency():
    header = 'date,time,symbol,side,quantity,price,asset_type,multiplier,quote_currency,quote_to_usd_rate\n'
    csv = header + '2026-10-02,10:00,USDJPY,SELL,.1,150,FOREX,100000,JPY,.0066\n2026-10-02,11:00,USDJPY,BUY,.1,149,FOREX,100000,JPY,.0067\n'
    trades, _ = parse_broker_csv(csv, 'generic', 1)
    assert trades[0]['gross_pnl'] == 67
    assert json.loads(trades[0]['executions'])[0]['multiplier'] == 100000
    with pytest.raises(ValueError, match='quote_to_usd_rate'):
        parse_broker_csv(csv.replace(',JPY,.0066', ',JPY,').replace(',JPY,.0067', ',JPY,'), 'generic', 1)


def test_exit_conversion_can_be_updated(db):
    trade = create_trade(TradeCreate(account_id=1, date='2026-10-02', ticker='USDJPY',
        instrument_type='FOREX', side='SHORT', quantity=.1, multiplier=100000,
        entry_price=150, exit_price=149, quote_currency='JPY', quote_to_usd_rate=.0066), db)
    updated = update_execution(trade['id'], 1,
        {'action': 'BOT', 'qty': .1, 'price': 149, 'commission': 0, 'quote_to_usd_rate': .0067}, db)
    assert updated['gross_pnl'] == 67
    assert json.loads(updated['executions'])[1]['multiplier'] == 100000


def test_existing_tos_trade_history_amounts():
    rows = [['', 'Exec Time', 'Spread', 'Side', 'Qty', 'Pos Effect', 'Symbol',
             'Exp', 'Strike', 'Type', 'Price', 'Net Price', 'Order Type'],
            ['', '10/02/2026 10:00:00', '', 'BUY', '2', '', 'SPY', '', '', 'STOCK', '600', '', ''],
            ['', '10/02/2026 10:00:00', '', 'BUY', '2', '', 'SPY', '16 OCT 26', '600', 'CALL', '3', '', '']]
    fills = parse_trade_history_section(rows)
    assert [fill['amount'] for fill in fills] == [-1200, -600]


def test_migration_preserves_custom_columns_indexes_ids_and_backup(tmp_path):
    path = tmp_path / 'old.db'
    conn = sqlite3.connect(path)
    conn.executescript("""CREATE TABLE accounts (id INTEGER PRIMARY KEY);
        INSERT INTO accounts VALUES(1);
        CREATE TABLE trades (id INTEGER PRIMARY KEY AUTOINCREMENT,
          account_id INTEGER REFERENCES accounts(id),
          instrument_type TEXT CHECK(instrument_type IN ('STOCK','OPTION','FUTURE')),
          setup TEXT, executions TEXT);
        CREATE INDEX idx_existing ON trades(setup);
        INSERT INTO trades VALUES(42,1,'STOCK','Retain me','[]');""")
    database.migrate_asset_types(conn)
    assert conn.execute('SELECT id,setup,executions FROM trades').fetchone() == (42,'Retain me','[]')
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='idx_existing'").fetchone()
    conn.execute("INSERT INTO trades(account_id,instrument_type) VALUES(1,'CRYPTO')")
    assert conn.execute('SELECT MAX(id) FROM trades').fetchone()[0] == 43
    assert Path(str(path) + '.before-multi-asset.bak').exists()
    database.migrate_asset_types(conn)
    assert conn.execute('SELECT COUNT(*) FROM trades').fetchone()[0] == 2
    conn.close()
