import { useState, useEffect } from 'react';

const KEY = 'libre.sourceTimezone';
const OPTIONS = [['auto', 'Auto'], ['UTC', 'UTC (+00:00)'], ['Asia/Manila', 'Philippine time (+08:00)'], ['America/New_York', 'New York'], ['Europe/London', 'London'], ['UTC+02:00', 'Fixed UTC+02:00'], ['UTC+03:00', 'Fixed UTC+03:00']];
function readClock() {
  try { const value = localStorage.getItem(KEY); return OPTIONS.some(([id]) => id === value) ? value : 'auto'; } catch { return 'auto'; }
}
export function useSourceClock() {
  const [value, setValue] = useState(readClock);
  useEffect(() => {
    const sync = () => setValue(readClock());
    window.addEventListener('storage', sync);
    window.addEventListener('libre-clock', sync);
    return () => { window.removeEventListener('storage', sync); window.removeEventListener('libre-clock', sync); };
  }, []);
  const change = next => {
    setValue(next);
    try { localStorage.setItem(KEY, next); window.dispatchEvent(new Event('libre-clock')); } catch { /* Keep this view usable when browser storage is unavailable. */ }
  };
  return [value, change];
}
export const originalClockLabel = clock => [clock.source, clock.label || clock.timezone || 'Unknown timezone'].filter(Boolean).join(' · ');
export function uniqueOriginalClocks(clocks = []) {
  return [...new Map(clocks.filter(Boolean).map(clock => [originalClockLabel(clock), clock])).values()];
}
export function OriginalEntry({ row, showClock = false }) {
  if (showClock && row.original_entries?.length) return <>{row.original_entries.map((entry, index) => <span className="trading-original-entry" key={`${entry.bucket}-${index}`}>{entry.bucket}<span className="trading-original-clock">{originalClockLabel(entry)}</span></span>)}</>;
  return <>{originalEntryLabels(row)}{showClock && row.original_clocks?.length > 0 && <span className="trading-original-clock">{uniqueOriginalClocks(row.original_clocks).map(originalClockLabel).join(', ')}</span>}</>;
}
export function SourceClockControl({ value, onChange, originalClocks = [] }) {
  const [expanded, setExpanded] = useState(false);
  const clocks = uniqueOriginalClocks(originalClocks);
  const manual = value !== 'auto';
  const clockLabel = OPTIONS.find(([id]) => id === value)?.[1] || value;
  return <div className="trading-clock">
    <div className="trading-clock-summary">
      {!manual && clocks.length > 0 && <span>Original: {clocks.length === 1 ? originalClockLabel(clocks[0]) : 'Multiple timezones / sources'} <span aria-hidden="true">→</span></span>}
      <span>Philippine time <span className="text-muted">(UTC+8)</span></span>
      {manual && <span className="trading-clock-override">Original timezone: {clockLabel}</span>}
      <button type="button" className="trading-clock-link" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>Adjust original timezone</button>
      {manual && <button type="button" className="trading-clock-link" onClick={() => onChange('auto')}>Reset to Auto</button>}
    </div>
    {expanded && <div className="trading-clock-settings">
    <label className="field-label">Original trade timezone
      <select aria-label="Original trade timezone" value={value} onChange={e => onChange(e.target.value)}>
        {OPTIONS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
      </select>
    </label>
    <p className="text-muted">Auto reads the timezone from your import. Change it only if the Philippine time is wrong. Applies to all views.</p>
    <p className="text-muted">Date filters use the original closing date.</p>
    </div>}
  </div>;
}
export function ConversionNotice({ conversion }) {
  if (!conversion?.unconverted_count) return null;
  return <p className="trading-clock-notice">{conversion.unconverted_count} trade{conversion.unconverted_count === 1 ? '' : 's'} missing a timezone or entry time. Not included in PHT totals; shown as Unclassified in sessions.</p>;
}
export const originalEntryLabels = row => row.original_buckets?.length ? row.original_buckets.join(', ') : '—';
const formatMoney = value => `${Number(value) < 0 ? '-' : ''}$${Math.abs(Number(value || 0)).toFixed(2)}`;
export function TimePerformanceTable({ rows = [], session = false }) {
  if (!rows.length) return <p className="text-muted">No converted entries in this range.</p>;
  const mixedClocks = uniqueOriginalClocks(rows.flatMap(row => row.original_clocks || [])).length > 1;
  return <div className="table-container"><table><thead><tr>{!session && <th>Original entry</th>}<th>{session ? 'Trading session' : 'Philippine time (PHT)'}</th><th>Trades</th><th>Net P&L</th><th>Win rate</th><th>Avg / trade</th></tr></thead><tbody>
    {rows.map(row => <tr key={row.session || row.bucket}>{!session && <td><OriginalEntry row={row} showClock={mixedClocks} /></td>}<td>{row.session || row.bucket}</td><td>{row.trade_count}</td><td className={row.net_pnl >= 0 ? 'pos' : 'neg'}>{formatMoney(row.net_pnl)}</td><td>{Number(row.win_rate).toFixed(1)}%</td><td>{formatMoney(row.avg_pnl)}</td></tr>)}
  </tbody></table></div>;
}
export const SESSION_NOTE = 'Sessions use entry time and historical daylight saving: Sydney 08:00–17:00, Tokyo 09:00–18:00, London 08:00–17:00, New York 08:00–17:00 in each city. Overlaps count once as a combined session. These are analysis windows, not exchange opening hours.';

export function SessionHours() {
  return <details className="trading-session-hours"><summary>Session hours</summary><p>{SESSION_NOTE}</p></details>;
}
