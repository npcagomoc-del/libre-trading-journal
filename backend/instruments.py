"""Shared sizing for journal P&L; quantity is units unless a contract size is given."""
import math

ASSET_TYPES = {'STOCK', 'OPTION', 'FUTURE', 'CRYPTO', 'FOREX', 'GOLD'}


def positive_number(value, label):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f'{label} must be a finite number above zero')
    return value


def default_multiplier(instrument, ticker):
    if instrument == 'OPTION':
        return 100
    if instrument == 'FUTURE':
        from csv_parser import FUTURES_MULTIPLIERS
        for root in sorted(FUTURES_MULTIPLIERS, key=len, reverse=True):
            if ticker.upper().lstrip('/').startswith(root.lstrip('/')):
                return FUTURES_MULTIPLIERS[root]
        raise ValueError('Enter the contract size for this futures symbol.')
    return 1


def sizing(instrument, ticker, values):
    multiplier = values.get('multiplier')
    if multiplier is None:
        multiplier = default_multiplier(instrument, ticker)
    currency = (values.get('quote_currency') or 'USD').upper().strip()
    rate = values.get('quote_to_usd_rate')
    if currency != 'USD' and rate is None:
        raise ValueError('Enter the quote-currency conversion to USD.')
    return {'multiplier': positive_number(multiplier, 'Contract size'),
            'quote_currency': currency,
            'quote_to_usd_rate': positive_number(rate if rate is not None else 1, 'USD conversion')}
