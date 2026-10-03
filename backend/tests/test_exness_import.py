import asyncio
import io
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import database
from csv_parser import detect_broker, parse_broker_csv
from main import import_csv, update_execution, add_execution, delete_execution

HEADER = 'ticket,symbol,side,lots,open_time,close_time,open_price,close_price,profit,commission,swap,stop_loss,take_profit,contract_size,account_currency,account_to_usd_rate,quote_to_usd_rate\n'
ROW = '2286321743,XAUUSD,sell,0.03,2026-09-28 11:47:00,2026-09-28 12:03:07,4153.961,4148.570,16.17,-0.33,0,4149.090,4145.536,100,USD,1,1\n'


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'test.db'))
    database.init_db()
    conn = database.get_db()
    conn.execute("INSERT INTO accounts (name,type) VALUES ('Exness test','day_trading')")
    conn.commit()
    yield conn
    conn.close()


def import_content(content, db):
    return asyncio.run(import_csv(account_id=1, file=UploadFile(filename='positions.csv', file=io.BytesIO(content.encode())), broker='exness', conn=db))


def test_broker_profit_fractional_lots_and_stops():
    assert detect_broker(HEADER + ROW) == 'exness'
    trades, skipped = parse_broker_csv(HEADER + ROW, 'auto', 7)
    trade = trades[0]
    assert skipped == 0
    assert trade['trade_group'] == 'exness_7_2286321743'
    # Displayed prices imply 16.173; preserve the broker's reported 16.17.
    assert (trade['gross_pnl'], trade['commissions'], trade['net_pnl']) == (16.17, .33, 15.84)
    fills = json.loads(trade['executions'])
    assert [fill['qty'] for fill in fills] == [.03, .03]
    assert fills[0]['multiplier'] == 100
    assert fills[0]['time'] == '11:47:00'
    assert fills[1]['time'] == '12:03:07'
    assert trade['stop_loss'] == 4149.09
    assert trade['target_price'] == 4145.536


@pytest.mark.parametrize('swap,expected', [(-2, 13.84), (1.5, 17.34)])
def test_signed_swap(swap, expected):
    row = ROW.replace(',-0.33,0,', f',-0.33,{swap},')
    trade = parse_broker_csv(HEADER + row, 'exness', 1)[0][0]
    assert trade['swaps'] == swap
    assert trade['net_pnl'] == expected


def test_duplicate_overlapping_tickets_and_overnight():
    other = ROW.replace('2286321743', '999').replace('2026-09-28 12:03:07', '2026-09-29 12:03:07')
    trades, skipped = parse_broker_csv(HEADER + ROW + other + ROW, 'exness', 1)
    assert len(trades) == 2 and skipped == 1
    assert trades[1]['date'] == '2026-09-29'
    assert json.loads(trades[1]['executions'])[0]['date'] == '2026-09-28'
    with pytest.raises(ValueError, match='conflicting duplicate'):
        parse_broker_csv(HEADER + ROW + ROW.replace('16.17', '17.00'), 'exness', 1)


def test_reimport_preserves_analysis_and_execution_metadata(db):
    assert import_content(HEADER + ROW, db)['imported'] == 1
    db.execute("UPDATE trade_analysis SET notes='My notes' WHERE trade_group='exness_1_2286321743'")
    db.commit()
    result = import_content(HEADER + ROW, db)
    assert result['imported'] == 0 and result['skipped'] == 1
    assert db.execute('SELECT COUNT(*) FROM trades').fetchone()[0] == 1
    assert db.execute('SELECT notes,stop_loss,target_price FROM trade_analysis').fetchone()[:] == ('My notes', 4149.09, 4145.536)
    trade = dict(db.execute('SELECT * FROM trades').fetchone())
    fill = json.loads(trade['executions'])[1]
    fill.update(time='12:04:00', commission=.5)
    result = update_execution(trade['id'], 1, fill, db)
    assert result['gross_pnl'] == 16.17 and result['net_pnl'] == 15.67
    assert json.loads(result['executions'])[1]['ticket'] == '2286321743'
    fill['price'] += 1
    with pytest.raises(HTTPException):
        update_execution(trade['id'], 1, fill, db)
    with pytest.raises(HTTPException):
        add_execution(trade['id'], fill, db)
    with pytest.raises(HTTPException):
        delete_execution(trade['id'], 1, db)
    assert import_content(HEADER + ROW, db)['imported'] == 1
    assert db.execute('SELECT notes FROM trade_analysis').fetchone()[0] == 'My notes'


def test_generic_import_cannot_regroup_broker_positions(db):
    import_content(HEADER + ROW, db)
    generic = 'date,time,symbol,side,quantity,price,asset_type,multiplier\n2026-09-28,11:48,XAUUSD,BUY,.03,4150,GOLD,100\n2026-09-28,12:00,XAUUSD,SELL,.03,4151,GOLD,100\n'
    trades, _ = parse_broker_csv(generic, 'generic', 1, db)
    assert len(trades) == 1 and trades[0]['gross_pnl'] == 3
    assert db.execute('SELECT gross_pnl FROM trades').fetchone()[0] == 16.17


def test_mt5_repeated_headers_and_suffix():
    text = 'Time;Position;Symbol;Type;Volume;Price;S / L;T / P;Time;Price;Commission;Swap;Profit\n2026.09.28 11:47:00;1;XAUUSDm;sell;0,03;4153,961;4149,090;4145,536;2026.09.28 12:03:07;4148,570;-0,33;0;16,17\n'
    trades, _ = parse_broker_csv(text, 'auto', 1)
    assert trades[0]['ticker'] == 'XAUUSDM' and trades[0]['net_pnl'] == 15.84


def test_comma_csv_thousands_and_symbol_correction(db):
    text = HEADER + ROW.replace('4153.961', '"4,153"').replace('16.17', '"4,153"')
    trade = parse_broker_csv(text, 'exness', 1)[0][0]
    assert trade['gross_pnl'] == 4153
    assert json.loads(trade['executions'])[0]['price'] == 4153
    import_content(HEADER + ROW, db)
    assert import_content(HEADER + ROW.replace('XAUUSD', 'EURUSD'), db)['imported'] == 1
    saved = db.execute('SELECT ticker,instrument_type FROM trades').fetchone()
    assert saved[:] == ('EURUSD', 'FOREX')


def test_nonusd_account_conversion_and_nonusd_quote():
    # Broker profit is in account currency, not the quote currency.
    text = HEADER + ROW.replace('XAUUSD', 'USDJPY').replace(',100,USD,1,1', ',100000,EUR,1.1,')
    trade = parse_broker_csv(text, 'exness', 1)[0][0]
    assert trade['gross_pnl'] == 17.79 and trade['commissions'] == .36
    assert trade['net_pnl'] == 17.43
    with pytest.raises(ValueError, match='account_to_usd_rate'):
        parse_broker_csv(text.replace(',EUR,1.1,', ',EUR,,'), 'exness', 1)


@pytest.mark.parametrize('old,new,error', [
    ('0.03', '-0.03', 'lots'), ('16.17', 'NaN', 'profit'),
    ('-0.33', '0.33', 'commission'), ('USD,1,1', 'USC,1,1', 'cent accounts'),
    ('2026-09-28 12:03:07', '2026-09-27 12:03:07', 'earlier'),
])
def test_invalid_row_stops_entire_import(db, old, new, error):
    with pytest.raises(ValueError, match=error):
        import_content(HEADER + ROW + ROW.replace('2286321743', '999').replace(old, new), db)
    assert db.execute('SELECT COUNT(*) FROM trades').fetchone()[0] == 0


def test_forex_contract_size_and_short_direction():
    row = '1,EURUSDm,sell,.1,2026-09-28 10:00:00,2026-09-28 11:00:00,1.102,1.100,20,-.70,0,,,,USD,1,1\n'
    trade = parse_broker_csv(HEADER + row, 'exness', 1)[0][0]
    assert trade['instrument_type'] == 'FOREX' and trade['net_pnl'] == 19.3
    assert json.loads(trade['executions'])[0]['multiplier'] == 100000


def test_native_export_utc_and_metadata():
    text = 'ticket,opening_time_utc,closing_time_utc,type,lots,original_position_size,symbol,opening_price,closing_price,stop_loss,take_profit,commission,swap,profit,equity,margin_level,close_reason\n1,2026-10-02T11:53:36,2026-10-02T11:58:12,buy,0.04,0.04,XAUUSD,4180.049,4182.657,4182.657,4187.59,-0.44,,10.43,,,sl\n'
    assert detect_broker(text) == 'exness'
    trade = parse_broker_csv(text, 'auto', 1)[0][0]
    assert trade['net_pnl'] == 9.99
    execution = json.loads(trade['executions'])[0]
    assert execution['timestamp_timezone'] == 'UTC'
    assert execution['original_position_size'] == .04
    assert execution['close_reason'] == 'sl'
    assert execution['take_profit'] == 4187.59
    with pytest.raises(ValueError, match='partial closes'):
        parse_broker_csv(text.replace('0.04,0.04', '0.02,0.04'), 'exness', 1)


def test_reimport_corrects_broker_stops_but_preserves_user_edits(db):
    import_content(HEADER + ROW, db)
    corrected = ROW.replace('4145.536', '4145.59')
    import_content(HEADER + corrected, db)
    assert db.execute('SELECT target_price FROM trade_analysis').fetchone()[0] == 4145.59
    db.execute("UPDATE trade_analysis SET stop_loss=4200,notes='Keep my journal notes'")
    db.commit()
    import_content(HEADER + corrected.replace('4149.090', '4149.100'), db)
    assert db.execute('SELECT stop_loss,notes FROM trade_analysis').fetchone()[:] == (4200, 'Keep my journal notes')
