import { render, screen, waitFor, act } from '@testing-library/react';
import { createChart } from 'lightweight-charts';
import TradingChart from './TradingChart';
import { chartApi } from '../api';

jest.mock('../api', () => ({ chartApi: { get: jest.fn() } }));
jest.mock('lightweight-charts', () => ({ createChart: jest.fn(), ColorType: { Solid: 0 }, CrosshairMode: { Normal: 0 }, LineStyle: { Solid: 0, Dashed: 1, Dotted: 2 } }));

let candles, chart;
beforeEach(() => {
  window.ResizeObserver = class { observe() {} disconnect() {} };
  candles = { setData: jest.fn(), setMarkers: jest.fn(), createPriceLine: jest.fn(), barsInLogicalRange: jest.fn() };
  const scale = { fitContent: jest.fn(), setVisibleRange: jest.fn(), subscribeVisibleLogicalRangeChange: jest.fn() };
  chart = { addCandlestickSeries: jest.fn(() => candles), addHistogramSeries: jest.fn(() => ({ setData: jest.fn() })),
    priceScale: () => ({ applyOptions: jest.fn() }), timeScale: () => scale, remove: jest.fn() };
  createChart.mockReturnValue(chart);
});
const bar = (t, o = 4100.123) => ({ t, o, h: 4102.345, l: 4100.001, c: 4101.234, v: 51 });
const data = { provider: 'mt5', feed_broker: 'ftmo', resolved_symbol: 'XAUUSD', price_digits: 3, utc_offset_hours: 0,
  bars: [bar('2026-10-01T23:55:00Z'), bar('2026-10-02T00:00:00Z')] };

test('MT5 chart preserves overnight fills, gold precision, UTC clock and reference attribution', async () => {
  chartApi.get.mockResolvedValue({ data });
  render(<TradingChart ticker="XAUUSD" instrumentType="GOLD" accountId={1} utcOffsetHours={0} tradeSource="exness" date="2026-10-02"
    executions={[{ date: '2026-10-01', time: '23:56:00', action: 'BOT', qty: .03, price: 4100.123 },
      { date: '2026-10-02', time: '00:01:00', action: 'SOLD', qty: .03, price: 4101.234 }]} />);
  await waitFor(() => expect(candles.setData).toHaveBeenCalled());
  expect(chartApi.get).toHaveBeenCalledWith('XAUUSD', '2026-10-02', '5Min', 2, 'GOLD', 1, 0);
  expect(chart.addCandlestickSeries).toHaveBeenCalledWith(expect.objectContaining({ priceFormat: { type: 'price', precision: 3, minMove: .001 } }));
  const times = candles.setData.mock.calls[0][0].map(b => b.time);
  expect(candles.setMarkers.mock.calls[0][0].map(m => m.time)).toEqual(times);
  expect(screen.getByText(/FTMO · XAUUSD · trade clock UTC\+0 · tick volume/)).toHaveTextContent('Reference prices may differ');
  expect(screen.queryByRole('button', { name: 'VWAP' })).not.toBeInTheDocument();
  expect(chart.timeScale().setVisibleRange).not.toHaveBeenCalled();
});

test('older account response cannot replace newly selected account prices', async () => {
  let resolveOld;
  chartApi.get.mockImplementation((ticker, date, tf, days, asset, account) => account === 1
    ? new Promise(resolve => { resolveOld = resolve; })
    : Promise.resolve({ data: { ...data, bars: [bar('2026-10-02T00:00:00Z', 5000)] } }));
  const { rerender } = render(<TradingChart ticker="XAUUSD" instrumentType="GOLD" date="2026-10-02" accountId={1} />);
  await waitFor(() => expect(chartApi.get).toHaveBeenCalled());
  rerender(<TradingChart ticker="XAUUSD" instrumentType="GOLD" date="2026-10-02" accountId={2} />);
  await waitFor(() => expect(candles.setData).toHaveBeenCalled());
  await act(async () => resolveOld({ data }));
  expect(candles.setData.mock.calls.at(-1)[0][0].open).toBe(5000);
});
