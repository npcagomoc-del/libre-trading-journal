"""Exness / MT5 closed-position CSVs. Broker results are authoritative.

This reads positions, not individual MT5 deals or pending orders. Values in
profit/commission/swap are in account currency; the journal uses USD.
"""
import csv
import io
import json
import re
from functools import partial
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


ALIASES = {
    'ticket': ('ticket', 'positionid', 'position', 'orderid', 'order', 'id'),
    'symbol': ('symbol', 'instrument', 'ticker'),
    'side': ('side', 'type', 'direction'),
    'lots': ('lots', 'volume', 'volumelots', 'quantity', 'size'),
    'open_time': ('opentime', 'openingtime', 'opendatetime', 'entrytime', 'timeopen', 'opendate', 'openingdatetime', 'openingtimeutc'),
    'close_time': ('closetime', 'closingtime', 'closedatetime', 'exittime', 'timeclose', 'closedate', 'closingdatetime', 'closingtimeutc'),
    'open_price': ('openprice', 'openingprice', 'entryprice', 'priceopen'),
    'close_price': ('closeprice', 'closingprice', 'exitprice', 'priceclose'),
    'profit': ('profit', 'grossprofit', 'grosspnl', 'pnl', 'pl'),
    'commission': ('commission', 'commissions'),
    'swap': ('swap', 'swaps'),
    'fee': ('fee', 'fees'),
    'stop_loss': ('sl', 'stoploss'),
    'take_profit': ('tp', 'takeprofit', 'targetprice'),
    'contract_size': ('contractsize', 'multiplier', 'unitsperlot'),
    'account_currency': ('accountcurrency', 'currency', 'profitcurrency'),
    'account_to_usd_rate': ('accounttousdrate',),
    'quote_to_usd_rate': ('quotetousdrate',),
    'original_position_size': ('originalpositionsize',),
    'close_reason': ('closereason',),
    'timestamp_timezone': ('timestamptimezone',),
}
REQUIRED = ('ticket', 'symbol', 'side', 'lots', 'open_time', 'close_time', 'open_price', 'close_price', 'profit')
CURRENCIES = {'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF', 'CNH', 'CNY', 'HKD', 'SGD', 'ZAR', 'TRY', 'MXN', 'NOK', 'SEK', 'DKK', 'PLN', 'HUF', 'CZK', 'RUB', 'THB'}


def header_map(cells):
    names = [re.sub(r'[^a-z0-9]', '', cell.lower().lstrip('\ufeff')) for cell in cells]
    cols = {key: next((i for i, name in enumerate(names) if name in aliases), None)
            for key, aliases in ALIASES.items()}
    # MT5 position tables repeat Time and Price for opening and closing.
    for name, pair in [('time', ('open_time', 'close_time')), ('price', ('open_price', 'close_price'))]:
        indices = [i for i, n in enumerate(names) if n == name]
        if len(indices) == 2:
            for key, index in zip(pair, indices):
                if cols[key] is None:
                    cols[key] = index
    return cols if all(cols[k] is not None for k in REQUIRED) else None


def read_rows(content, with_delimiter=False):
    sample = content.lstrip('\ufeff')
    try:
        dialect = csv.Sniffer().sniff(sample[:8192], delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(sample), dialect))
    return (rows, dialect.delimiter) if with_delimiter else rows


def is_exness_csv(content):
    return any(header_map(row) for row in read_rows(content)[:20])


def number(value, name, default=None, positive=False, decimal_comma=False):
    if not value.strip() and default is not None:
        return Decimal(str(default))
    try:
        # Spaces are MT5 thousands separators. A comma decimal is allowed in a
        # semicolon/tab CSV; comma-thousands values must be quoted in comma CSV.
        text = value.strip().replace('\u00a0', '').replace(' ', '')
        if ',' in text and '.' not in text and decimal_comma:
            text = text.replace(',', '.')
        else:
            if ',' in text and not re.fullmatch(r'[+-]?\d{1,3}(,\d{3})+(\.\d+)?', text):
                raise InvalidOperation
            text = text.replace(',', '')
        result = Decimal(text)
        if not result.is_finite() or (positive and result <= 0):
            raise InvalidOperation
        return result
    except (InvalidOperation, ValueError):
        raise ValueError(f'{name} must be a finite' + (' positive' if positive else '') + ' number') from None


def timestamp(value, name):
    text = value.strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y.%m.%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y.%m.%d %H:%M', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError(f'{name} needs YYYY-MM-DD HH:MM:SS (or MT5 YYYY.MM.DD HH:MM:SS)')


def money(value):
    return float(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def parse_exness_csv(content, account_id, conn=None):
    rows, delimiter = read_rows(content, with_delimiter=True)
    numeric = partial(number, decimal_comma=delimiter != ',')
    found = next(((i, header_map(row)) for i, row in enumerate(rows[:20]) if header_map(row)), None)
    if not found:
        raise ValueError('Exness needs a closed-position CSV: ticket, symbol, side, lots, open_time, close_time, open_price, close_price, profit. Use the Exness template; MT5 deals/HTML are not position CSVs.')
    start, cols = found
    trades, seen, errors = [], {}, []
    skipped = 0
    for line, row in enumerate(rows[start + 1:], start + 2):
        if not any(c.strip() for c in row):
            continue
        def cell(key):
            i = cols.get(key)
            return row[i].strip() if i is not None and i < len(row) else ''
        try:
            ticket = cell('ticket').lstrip('#')
            if not re.fullmatch(r'\d+', ticket):
                raise ValueError('ticket must be a numeric position ID, stored as text')
            symbol = cell('symbol').upper()
            # Account suffixes such as EURUSDm and XAUUSDc stay visible.
            base = re.match(r'^([A-Z]{6})(?:[A-Z0-9._-]*)$', symbol)
            base = base.group(1) if base else ''
            if base.startswith('XAU') and base[3:] in CURRENCIES:
                instrument, default_size = 'GOLD', 100
            elif base[:3] in CURRENCIES and base[3:] in CURRENCIES:
                instrument, default_size = 'FOREX', 100000
            else:
                raise ValueError(f'{symbol!r} is not a supported forex/gold symbol')
            side = cell('side').lower()
            if side not in ('buy', 'sell', 'long', 'short'):
                raise ValueError('side must be buy or sell; pending orders/deals are not closed positions')
            long = side in ('buy', 'long')
            lots = numeric(cell('lots'), 'lots', positive=True)
            original_size = numeric(cell('original_position_size'), 'original_position_size', positive=True) if cell('original_position_size') else None
            if original_size is not None and original_size != lots:
                raise ValueError('partial closes need reconciliation before import: lots differs from original_position_size')
            size = numeric(cell('contract_size'), 'contract_size', default_size, positive=True)
            entry = numeric(cell('open_price'), 'open_price', positive=True)
            exit_price = numeric(cell('close_price'), 'close_price', positive=True)
            opened = timestamp(cell('open_time'), 'open_time')
            closed = timestamp(cell('close_time'), 'close_time')
            if closed < opened:
                raise ValueError('close_time cannot be earlier than open_time')
            currency = cell('account_currency').upper() or 'USD'
            if currency not in CURRENCIES:
                raise ValueError('account_currency must be an ISO currency; cent accounts (USC/EUC) need conversion to a standard currency first')
            if currency != 'USD' and not cell('account_to_usd_rate'):
                raise ValueError('non-USD account money needs account_to_usd_rate')
            rate = numeric(cell('account_to_usd_rate'), 'account_to_usd_rate', 1, positive=True)
            if currency == 'USD' and rate != 1:
                raise ValueError('USD account_to_usd_rate must be 1')
            reported = numeric(cell('profit'), 'profit')
            signed_commission = numeric(cell('commission'), 'commission', 0)
            if signed_commission > 0:
                raise ValueError('commission must be a signed Exness charge (negative or zero), not a positive fee')
            fee = abs(numeric(cell('fee'), 'fee', 0))
            commission = -signed_commission + fee
            swap = numeric(cell('swap'), 'swap', 0)
            stop = numeric(cell('stop_loss'), 'stop_loss', 0)
            target = numeric(cell('take_profit'), 'take_profit', 0)
            if stop < 0 or target < 0:
                raise ValueError('stop_loss / take_profit cannot be negative')
            quote_rate = numeric(cell('quote_to_usd_rate'), 'quote_to_usd_rate', 1, positive=True) if cell('quote_to_usd_rate') or base[3:] == 'USD' else None
            if base[3:] == 'USD' and quote_rate != 1:
                raise ValueError('USD quote_to_usd_rate must be 1')
            metadata = dict(broker='exness', ticket=ticket, multiplier=float(size), quote_currency=base[3:],
                            account_currency=currency, account_to_usd_rate=float(rate),
                            broker_profit=float(reported), broker_commission=float(signed_commission),
                            broker_swap=float(swap), stop_loss=float(stop), take_profit=float(target))
            if original_size is not None:
                metadata['original_position_size'] = float(original_size)
            if cell('close_reason'):
                metadata['close_reason'] = cell('close_reason')
            utc_header = any(re.sub(r'[^a-z0-9]', '', c.lower()) in ('openingtimeutc', 'closingtimeutc') for c in rows[start])
            if utc_header or cell('timestamp_timezone'):
                metadata['timestamp_timezone'] = 'UTC' if utc_header else cell('timestamp_timezone')
            if quote_rate is not None:
                metadata['quote_to_usd_rate'] = float(quote_rate)
            execs = [dict(metadata, date=opened.date().isoformat(), time=opened.time().isoformat(),
                          action='BOT' if long else 'SOLD', qty=float(lots), price=float(entry), commission=0),
                     dict(metadata, date=closed.date().isoformat(), time=closed.time().isoformat(),
                          action='SOLD' if long else 'BOT', qty=float(lots), price=float(exit_price), commission=money(commission * rate))]
            trade = dict(account_id=account_id, trade_group=f'exness_{account_id}_{ticket}',
                         ticker=symbol, instrument_type=instrument, side='LONG' if long else 'SHORT',
                         date=closed.date().isoformat(), gross_pnl=money(reported * rate),
                         commissions=money(commission * rate), swaps=money(swap * rate),
                         net_pnl=round(money(reported * rate) - money(commission * rate) + money(swap * rate), 2), executions=json.dumps(execs),
                         option_expiry=None, option_strike=None, option_type=None, source='exness',
                         stop_loss=float(stop) or None, target_price=float(target) or None)
            if ticket in seen:
                if seen[ticket] != trade:
                    raise ValueError(f'conflicting duplicate ticket {ticket}; partial closes need distinct position/close records, not duplicate ticket rows')
                skipped += 1
                continue
            seen[ticket] = trade
            if conn:
                old = conn.execute('SELECT executions,ticker,instrument_type,gross_pnl,commissions,swaps,net_pnl FROM trades WHERE trade_group=? AND account_id=?',
                                   (trade['trade_group'], account_id)).fetchone()
                if old and json.loads(old[0]) == execs and tuple(old)[1:] == tuple(trade[k] for k in ('ticker', 'instrument_type', 'gross_pnl', 'commissions', 'swaps', 'net_pnl')):
                    skipped += 1
                    continue
            trades.append(trade)
        except ValueError as error:
            errors.append(f'line {line}: {error}')
    if errors:
        raise ValueError('Exness import stopped; no trades were imported. ' + '; '.join(errors[:8]))
    if not seen:
        raise ValueError('This Exness CSV contains no closed positions.')
    return trades, skipped
