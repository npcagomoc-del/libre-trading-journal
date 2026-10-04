import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { Patterns } from '../v3/DashboardRender';
import Trades from './Trades';
import { tradesApi } from '../api';
import { useSourceClock, SourceClockControl, TimePerformanceTable, ConversionNotice } from './TradingTime';
jest.mock('../api', () => ({ tradesApi: { list: jest.fn(), listCustomSetups: jest.fn() } }));
beforeEach(() => { localStorage.clear(); tradesApi.listCustomSetups.mockResolvedValue({ data: [] }); });
test('Philippine rows preserve next-day date and display unknown clocks honestly', async () => {
 tradesApi.list.mockResolvedValue({ data: [
  { id: 1, date: '2026-10-02', ticker: 'XAUUSD', side: 'LONG', executions: [], net_pnl: 10, entry_ph_time: { date: '2026-10-03', time: '00:30:00', utc: '2026-10-02T16:30:00Z', session: 'London + New York' } },
  { id: 2, date: '2026-10-02', ticker: 'UNKNOWN', executions: [], entry_time_status: 'unknown_clock' }
 ] });
 render(<Trades onOpenDetail={() => {}} />);
 expect(await screen.findByText('00:30 PHT (12:30 AM)')).toBeInTheDocument();
 expect(screen.getByText('2026-10-03')).toBeInTheDocument();
 expect(screen.getByText('London + New York')).toBeInTheDocument();
 expect(screen.getByText('Set source clock')).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button', { name: 'Adjust original timezone' }));
 fireEvent.change(screen.getByLabelText('Original trade timezone'), { target: { value: 'UTC' } });
 await waitFor(() => expect(tradesApi.list).toHaveBeenLastCalledWith({ source_timezone: 'UTC' }));
 expect(localStorage.getItem('libre.sourceTimezone')).toBe('UTC');
});
test('patterns use Philippine buckets and combined sessions with conversion exclusions', () => {
 render(<Patterns edge={{ philippine_time_of_day: [{ bucket: '19:30', original_buckets: ['11:30', '14:30'], trade_count: 2, net_pnl: 10, win_rate: 50 }], time_of_day: [{ bucket: '11:30', trade_count: 2 }], trading_sessions: [{ session: 'London + New York', trade_count: 2, net_pnl: 10, win_rate: 50 }], time_conversion: { converted_count: 2, unconverted_count: 1 } }} />);
 expect(screen.getByText('19:30')).toBeInTheDocument();
 const row = screen.getByText('19:30').closest('tr');
 expect(within(row).getAllByRole('cell')[0]).toHaveTextContent('11:30, 14:30');
 expect(within(row).getAllByRole('cell')[1]).toHaveTextContent('19:30');
 expect(screen.getByText(/1 trade missing a timezone or entry time/)).toBeInTheDocument();
 fireEvent.click(screen.getByRole('tab', { name: 'Trading sessions' }));
 expect(within(screen.getByRole('table')).getByText('London + New York')).toBeInTheDocument();
 expect(screen.getByText('50%')).toBeInTheDocument();
});
test('source preference synchronizes mounted views', () => {
 function Control() { const [value, change] = useSourceClock(); return <SourceClockControl value={value} onChange={change} />; }
 render(<><Control /><Control /></>);
 screen.getAllByRole('button', { name: 'Adjust original timezone' }).forEach(button => fireEvent.click(button));
 const controls = screen.getAllByLabelText('Original trade timezone');
 fireEvent.change(controls[0], { target: { value: 'Asia/Manila' } });
 expect(controls[1]).toHaveValue('Asia/Manila');
});

test('overnight SHORT records the prior-day SOLD entry rather than the next-day BOT exit', async () => {
 tradesApi.list.mockResolvedValue({ data: [{ id: 5, date: '2026-10-03', ticker: 'XAUUSD', side: 'SHORT', net_pnl: 3,
  executions: [{ date: '2026-10-03', time: '00:03:00', action: 'BOT' }, { date: '2026-10-02', time: '23:53:00', action: 'SOLD' }],
  entry_ph_time: { date: '2026-10-03', time: '07:53:00', utc: '2026-10-02T23:53:00Z', session: 'Sydney' }
 }] });
 render(<Trades onOpenDetail={() => {}} />);
 const row = (await screen.findByText('XAUUSD')).closest('tr');
 const cells = within(row).getAllByRole('cell');
 expect(cells[0]).toHaveTextContent('2026-10-02');
 expect(cells[0]).toHaveTextContent('23:53');
 expect(cells[0]).not.toHaveTextContent('00:03');
 expect(cells[1]).toHaveTextContent('2026-10-03');
 expect(cells[1]).toHaveTextContent('07:53 PHT (7:53 AM)');
});


test('Auto stays quiet, persisted overrides remain visible and can be reset while collapsed', () => {
 localStorage.setItem('libre.sourceTimezone', 'UTC');
 function Control() { const [value, change] = useSourceClock(); return <SourceClockControl value={value} onChange={change} />; }
 render(<><Control /><ConversionNotice conversion={{ converted_count: 81, unconverted_count: 0 }} /></>);
 expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
 expect(screen.getByText('Original timezone: UTC (+00:00)')).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button', { name: 'Reset to Auto' }));
 expect(localStorage.getItem('libre.sourceTimezone')).toBe('auto');
 expect(screen.queryByText(/Original timezone:/)).not.toBeInTheDocument();
 expect(screen.queryByText(/81 trades/)).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button', { name: 'Adjust original timezone' }));
 expect(screen.getByLabelText('Original trade timezone')).toHaveValue('auto');
});

test('report time rows pair actual original buckets with PHT and keep missing source labels honest', () => {
 render(<TimePerformanceTable rows={[
  { bucket: '00:30', original_buckets: ['16:30'], trade_count: 1, net_pnl: 10, win_rate: 100, avg_pnl: 10 },
  { bucket: '19:30', original_buckets: ['11:30', '14:30'], trade_count: 2, net_pnl: 4, win_rate: 50, avg_pnl: 2 },
  { bucket: '20:00', trade_count: 1, net_pnl: 0, win_rate: 0, avg_pnl: 0 },
 ]} />);
 const rows = screen.getAllByRole('row');
 expect(within(rows[1]).getAllByRole('cell')[0]).toHaveTextContent('16:30');
 expect(within(rows[1]).getAllByRole('cell')[1]).toHaveTextContent('00:30');
 expect(within(rows[2]).getAllByRole('cell')[0]).toHaveTextContent('11:30, 14:30');
 expect(within(rows[3]).getAllByRole('cell')[0]).toHaveTextContent('—');
});


test('automatic Exness timezone is named, while an override never claims Exness UTC', () => {
 const clocks = [{ source: 'Exness', timezone: 'UTC', label: 'UTC+0' }];
 const { rerender } = render(<SourceClockControl value="auto" onChange={() => {}} originalClocks={clocks} />);
 expect(screen.getByText(/Original: Exness · UTC\+0/)).toBeInTheDocument();
 expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
 rerender(<SourceClockControl value="UTC+02:00" onChange={() => {}} originalClocks={clocks} />);
 expect(screen.queryByText(/Exness · UTC\+0/)).not.toBeInTheDocument();
 expect(screen.getByText('Original timezone: Fixed UTC+02:00')).toBeInTheDocument();
});

test('mixed original clocks are labeled next to their original entries', () => {
 render(<TimePerformanceTable rows={[
  { bucket: '19:30', original_buckets: ['11:30'], original_clocks: [{ source: 'Exness', timezone: 'UTC', label: 'UTC+0' }], trade_count: 1, net_pnl: 10, win_rate: 100, avg_pnl: 10 },
  { bucket: '20:30', original_buckets: ['08:30'], original_clocks: [{ source: 'CSV', timezone: 'America/New_York', label: 'New York (UTC−4)' }], trade_count: 1, net_pnl: 4, win_rate: 100, avg_pnl: 4 },
 ]} />);
 const row = screen.getByText('19:30').closest('tr');
 expect(within(row).getAllByRole('cell')[0]).toHaveTextContent('11:30Exness · UTC+0');
 expect(screen.getByText('CSV · New York (UTC−4)')).toBeInTheDocument();
});


test('a shared PHT bucket pairs each source hour with its own clock', () => {
 render(<TimePerformanceTable rows={[{ bucket: '19:30', original_buckets: ['11:30', '07:30'],
  original_clocks: [{ source: 'Exness', label: 'UTC+0' }, { source: 'CSV', label: 'UTC−4' }],
  original_entries: [{ bucket: '11:30', source: 'Exness', label: 'UTC+0' }, { bucket: '07:30', source: 'CSV', label: 'UTC−4' }],
  trade_count: 2, net_pnl: 10, win_rate: 50, avg_pnl: 5,
 }]} />);
 expect(screen.getByText('Exness · UTC+0').parentElement).toHaveTextContent('11:30');
 expect(screen.getByText('CSV · UTC−4').parentElement).toHaveTextContent('07:30');
});
