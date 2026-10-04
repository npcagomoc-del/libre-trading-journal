import { render, waitFor } from '@testing-library/react';
import DashboardRender from './DashboardRender';
import { calendarApi } from '../api';

jest.mock('../api', () => ({ calendarApi: { get: jest.fn() } }));

beforeEach(() => calendarApi.get.mockResolvedValue({ data: [] }));

test.each([
  [41.60, '+$41.60'],
  [-41.60, '−$41.60'],
  [-0.60, '−$0.60'],
  [999.999, '+$1,000.00'],
])('dashboard headline preserves dollars and cents for %s', async (net, expected) => {
  const { container } = render(<DashboardRender kpis={{ total_net_pnl: net }} recentTrades={[]} />);
  expect(container.querySelector('h1.v3-money').textContent).toBe(expected);
  await waitFor(() => expect(calendarApi.get).toHaveBeenCalled());
});
