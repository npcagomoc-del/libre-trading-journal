import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ChatGPTConnection from './ChatGPTConnection';
import { aiApi } from '../api';

jest.mock('../api', () => ({
  API_BASE: 'http://localhost:8010',
  aiApi: { status: jest.fn(), models: jest.fn(), connect: jest.fn(), verify: jest.fn() },
}));

beforeEach(() => {
  aiApi.status.mockResolvedValue({ data: { connected: false, plan_usage_enabled: false, registrations: [] } });
  aiApi.models.mockResolvedValue({ data: { models: [{ slug: 'available', display_name: 'Available model' }] } });
});

test('opens a backend sign-in ticket without frontend credentials', async () => {
  const popup = { location: {}, close: jest.fn() };
  const open = jest.spyOn(window, 'open').mockReturnValue(popup);
  aiApi.connect.mockResolvedValue({ data: { start_path: '/auth/start?ticket=local-ticket' } });
  render(<ChatGPTConnection />);
  await screen.findByText('Connect your ChatGPT account to use Brain and AI coaching.');
  fireEvent.click(screen.getByRole('button', { name: 'Continue with ChatGPT' }));
  await waitFor(() => expect(popup.location.href).toBe('http://localhost:8010/auth/start?ticket=local-ticket'));
  expect(popup.opener).toBeNull();
  expect(screen.getByText(/Complete sign-in in the new tab/)).toBeInTheDocument();
  open.mockRestore();
});

test('shows plan permission requirement after identity-only sign-in', async () => {
  aiApi.status.mockResolvedValue({ data: { connected: true, plan_usage_enabled: false } });
  render(<ChatGPTConnection />);
  expect(await screen.findByText(/permission to use your ChatGPT plan was not granted/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Test connection' })).not.toBeInTheDocument();
});

test('displays usage limit errors and does not claim verification', async () => {
  aiApi.status.mockResolvedValue({ data: { connected: true, plan_usage_enabled: true, model: 'available', verification: 'not_tested' } });
  aiApi.verify.mockRejectedValue({ response: { data: { detail: 'Your ChatGPT plan limit has been reached.' } } });
  render(<ChatGPTConnection />);
  fireEvent.click(await screen.findByRole('button', { name: 'Test connection' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Your ChatGPT plan limit has been reached.');
  expect(screen.getByText(/Test the connection to verify account access/)).toBeInTheDocument();
});
