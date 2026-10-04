"""Read-only entry clock conversion and disjoint forex session analytics."""
import json
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SOURCE_CLOCKS = ('auto', 'UTC', 'Asia/Manila', 'America/New_York', 'Europe/London',
                 'UTC+02:00', 'UTC+03:00')
PH = timezone(timedelta(hours=8))
SESSIONS = (('Sydney', 'Australia/Sydney', 8, 17),
            ('Tokyo', 'Asia/Tokyo', 9, 18),
            ('London', 'Europe/London', 8, 17),
            ('New York', 'America/New_York', 8, 17))


def original_clock_label(trade, entry, name, timestamp):
    source = trade.get('source') or entry.get('broker') or 'imported'
    source = {'exness': 'Exness', 'generic': 'CSV', 'manual': 'Manual',
              'tos': 'Thinkorswim', 'ibkr': 'IBKR', 'imported': 'Import'}.get(source, source)
    minutes = int(timestamp.utcoffset().total_seconds() / 60)
    hours, remainder = divmod(abs(minutes), 60)
    offset = f"UTC{'+' if minutes >= 0 else '-'}{hours}" + (f':{remainder:02d}' if remainder else '')
    city = {'America/New_York': 'New York', 'Europe/London': 'London', 'Asia/Manila': 'Manila'}.get(name)
    return dict(source=source, timezone=name, label=f'{city} ({offset})' if city else offset)


def clock_zone(name):
    if name in ('UTC', 'UTC+0', 'UTC+00:00', 'GMT', 'Z'):
        return timezone.utc
    match = re.fullmatch(r'UTC([+-])(\d{1,2})(?::(\d{2}))?', name or '')
    if match:
        hours, minutes = int(match[2]), int(match[3] or 0)
        if hours > 14 or minutes > 59 or (hours == 14 and minutes):
            raise ValueError('Invalid UTC offset')
        return timezone(timedelta(minutes=(hours * 60 + minutes) * (1 if match[1] == '+' else -1)))
    return ZoneInfo(name)


def session_at(instant):
    active = []
    for label, zone, start, end in SESSIONS:
        local = instant.astimezone(ZoneInfo(zone))
        if local.weekday() < 5 and start <= local.hour < end:
            active.append(label)
    return ' + '.join(active) or 'Outside sessions'


def entry_clock(trade, source_timezone='auto'):
    executions = trade.get('executions') or []
    if isinstance(executions, str):
        try:
            executions = json.loads(executions)
        except (ValueError, TypeError):
            return None, 'invalid_timestamp'
    if not isinstance(executions, list):
        return None, 'invalid_timestamp'
    action = 'SOLD' if (trade.get('side') or 'LONG').upper() == 'SHORT' else 'BOT'
    entries = [e for e in executions if isinstance(e, dict) and e.get('action') == action]
    if not entries:
        return None, 'missing_entry'
    instants = []
    clocks = []
    originals = []
    for entry in entries:
        if not entry.get('date') or not entry.get('time'):
            return None, 'missing_entry'
        try:
            timestamp = datetime.fromisoformat(f"{entry['date']}T{entry['time']}")
        except (ValueError, TypeError):
            return None, 'invalid_timestamp'
        clock = source_timezone
        if source_timezone == 'auto':
            clock = entry.get('timestamp_timezone')
            if not clock and (trade.get('source') == 'exness' or entry.get('broker') == 'exness'):
                clock = 'UTC'
            if timestamp.tzinfo is not None:
                clock = str(timestamp.tzinfo)
            elif not clock:
                return None, 'unknown_clock'
        try:
            if timestamp.tzinfo is None:
                zone = clock_zone(clock)
                timestamp = timestamp.replace(tzinfo=zone)
                # Refuse ambiguous/nonexistent local times instead of guessing a DST fold.
                if timestamp.utcoffset() != timestamp.replace(fold=1).utcoffset():
                    return None, 'ambiguous_timestamp'
                if timestamp.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != timestamp.replace(tzinfo=None):
                    return None, 'invalid_timestamp'
            instants.append(timestamp.astimezone(timezone.utc))
            clocks.append(clock)
            originals.append(timestamp)
        except (ValueError, KeyError, TypeError):
            return None, 'unknown_clock'
    index = min(range(len(instants)), key=instants.__getitem__)
    instant = instants[index]
    local = instant.astimezone(PH)
    original_clock = original_clock_label(trade, entries[index], clocks[index], originals[index])
    return dict(date=local.date().isoformat(), time=local.strftime('%H:%M'),
                original_date=originals[index].date().isoformat(),
                original_time=originals[index].strftime('%H:%M'),
                original_clock=original_clock,
                source_timezone=clocks[index], utc=instant.isoformat(), session=session_at(instant)), 'ok'


def philippine_performance(trades, source_timezone='auto'):
    hours = {f'{hour:02d}:{minute:02d}': [] for hour in range(24) for minute in (0, 30)}
    original_buckets = {key: set() for key in hours}
    original_clocks = {key: {} for key in hours}
    original_entries = {key: {} for key in hours}
    all_clocks = {}
    sessions = {}
    converted = 0
    for trade in trades:
        entry, _ = entry_clock(trade, source_timezone)
        pnl = trade.get('net_pnl') or 0
        if entry:
            converted += 1
            hour, minute = map(int, entry['time'].split(':'))
            bucket = f'{hour:02d}:{minute // 30 * 30:02d}'
            hours[bucket].append(pnl)
            original_hour, original_minute = map(int, entry['original_time'].split(':'))
            original_buckets[bucket].add(f'{original_hour:02d}:{original_minute // 30 * 30:02d}')
            descriptor = entry['original_clock']
            clock_key = (descriptor['source'], descriptor['timezone'], descriptor['label'])
            original_clocks[bucket][clock_key] = descriptor
            source_bucket = f'{original_hour:02d}:{original_minute // 30 * 30:02d}'
            original_entries[bucket][(source_bucket, *clock_key)] = dict(bucket=source_bucket, **descriptor)
            all_clocks[clock_key] = descriptor
            session = entry['session']
        else:
            session = 'Unclassified'
        sessions.setdefault(session, []).append(pnl)

    def stats(values):
        count = len(values)
        total = sum(values)
        return dict(trade_count=count, net_pnl=round(total, 2),
                    win_rate=round(sum(p > 0 for p in values) / count * 100, 1) if count else 0,
                    avg_pnl=round(total / count, 2) if count else 0)

    return dict(philippine_time_of_day=[dict(bucket=key, original_buckets=sorted(original_buckets[key]),
                                           original_clocks=[value for _, value in sorted(original_clocks[key].items())],
                                           original_entries=[value for _, value in sorted(original_entries[key].items())],
                                           **stats(values)) for key, values in hours.items()],
                trading_sessions=[dict(session=key, **stats(values)) for key, values in sorted(sessions.items())],
                time_conversion=dict(timezone='Asia/Manila', source_timezone=source_timezone,
                                     original_clocks=[value for _, value in sorted(all_clocks.items())],
                                     converted_count=converted, unconverted_count=len(trades) - converted))
