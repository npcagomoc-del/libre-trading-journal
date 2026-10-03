import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import MarketDataConnection from './MarketDataConnection';
import { marketDataApi } from '../api';

jest.mock('../api', () => ({ marketDataApi: { status: jest.fn(), connect: jest.fn(), disconnect: jest.fn() } }));
const accounts = [{ id: 1, name: 'Exness journal' }, { id: 2, name: 'FTMO journal' }];
const config = { broker: 'ftmo', path: 'C:/MT5/terminal64.exe', utc_offset_hours: 0, test_symbol: 'XAUUSD', server: 'FTMO-Demo', account_label: 'Account ending 5678' };
beforeEach(() => marketDataApi.status.mockResolvedValue({ data: { config: null, installations: [config.path] } }));

test('retains the Python terminal connection without needing an MCP key', async () => {
  marketDataApi.connect.mockResolvedValue({ data: { config, message: 'Retrieved 10 test candles.' } });
  render(<MarketDataConnection accounts={accounts} accountId={1} />);
  const button = screen.getByRole('button', { name: 'Connect & test MT5' });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Connection method'), { target: { value: 'terminal' } });
  fireEvent.change(screen.getByLabelText('MT5 price provider'), { target: { value: 'ftmo' } });
  fireEvent.click(button);
  await waitFor(() => expect(marketDataApi.connect).toHaveBeenCalledWith(1, expect.objectContaining({
    broker: 'ftmo', path: config.path, utc_offset_hours: 0, test_symbol: 'XAUUSD',
    transport: 'terminal',
  })));
  expect(await screen.findByText('Retrieved 10 test candles.')).toBeInTheDocument();
  expect(screen.getByText(/Saved feed: FTMO/)).toHaveTextContent('Account ending 5678');
  expect(screen.queryByLabelText(/password|api key/i)).not.toBeInTheDocument();
  expect(marketDataApi.connect.mock.calls.at(-1)[1]).not.toHaveProperty('mcp_api_key');
});

test('native MCP sends the masked key once and clears it after saving', async () => {
  const mcpConfig = { ...config, transport: 'mcp', broker: 'fundednext', has_key: true, server: 'FundedNext-Server 2' };
  marketDataApi.connect.mockResolvedValue({ data: { config: mcpConfig, message: 'MCP connected.' } });
  render(<MarketDataConnection accounts={accounts} accountId={1} />);
  const button = screen.getByRole('button', { name: 'Connect & test MT5' });
  await waitFor(() => expect(button).toBeEnabled());
  const key = screen.getByLabelText('MT5 MCP access key');
  expect(key).toHaveAttribute('type', 'password');
  fireEvent.change(key, { target: { value: 'test-local-key' } });
  fireEvent.click(button);
  await waitFor(() => expect(marketDataApi.connect).toHaveBeenLastCalledWith(1, expect.objectContaining({
    transport: 'mcp', broker: 'fundednext', mcp_api_key: 'test-local-key',
    mcp_url: 'http://127.0.0.1:22346/mcp', server_utc_offset_hours: 3, utc_offset_hours: 0,
  })));
  expect(await screen.findByText('MCP connected.')).toBeInTheDocument();
  expect(key).toHaveValue('');
  expect(key).toHaveAttribute('placeholder', 'Saved securely · leave blank to reuse');
  fireEvent.click(button);
  await waitFor(() => expect(marketDataApi.connect).toHaveBeenLastCalledWith(1, expect.objectContaining({ mcp_api_key: undefined })));
});

test('failed connection displays an actionable error without a saved feed', async () => {
  marketDataApi.connect.mockRejectedValue({ response: { data: { detail: 'Sign into MT5 first.' } } });
  render(<MarketDataConnection accounts={accounts} accountId={1} />);
  const button = screen.getByRole('button', { name: 'Connect & test MT5' });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  expect(await screen.findByRole('alert')).toHaveTextContent('Sign into MT5 first.');
  expect(screen.queryByText(/Saved feed:/)).not.toBeInTheDocument();
});

test('switching journal accounts clears previous feed and disconnect is account scoped', async () => {
  marketDataApi.status.mockImplementation(id => Promise.resolve({ data: { config: id === 1 ? config : null, installations: [] } }));
  marketDataApi.disconnect.mockResolvedValue({ data: { disconnected: true } });
  render(<MarketDataConnection accounts={accounts} accountId={1} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Disconnect market data' }));
  await waitFor(() => expect(marketDataApi.disconnect).toHaveBeenCalledWith(1));
  fireEvent.change(screen.getByLabelText('Journal account'), { target: { value: '2' } });
  await waitFor(() => expect(marketDataApi.status).toHaveBeenCalledWith(2));
  expect(screen.queryByText(/Saved feed:/)).not.toBeInTheDocument();
});
