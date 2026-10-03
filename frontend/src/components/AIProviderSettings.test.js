import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AIProviderSettings, { AIProviderStatus } from './AIProviderSettings';
import { aiProvidersApi } from '../api';

jest.mock('../api', () => ({ aiProvidersApi: { list: jest.fn(), select: jest.fn(), configure: jest.fn(), remove: jest.fn(), models: jest.fn(), verify: jest.fn() } }));
jest.mock('./ChatGPTConnection', () => () => <div>ChatGPT sign-in panel</div>);

const openai = { id: 'openai', label: 'OpenAI', configured: true, key_present: true, model: 'model-one', supports_images: true };
const summary = (provider = openai) => ({ data: { active_provider: provider.id, providers: [provider, { id: 'chatgpt', configured: false }] } });
beforeEach(() => {
  aiProvidersApi.list.mockResolvedValue(summary());
  aiProvidersApi.configure.mockResolvedValue({ data: {} });
  aiProvidersApi.remove.mockResolvedValue({ data: {} });
  aiProvidersApi.verify.mockResolvedValue({ data: { response: 'ok' } });
});

test('changing model preserves the saved API key and never calls inference', async () => {
  render(<AIProviderSettings />);
  fireEvent.change(await screen.findByLabelText('Model ID'), { target: { value: 'model-two' } });
  expect(screen.getByRole('button', { name: 'Test connection' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }));
  await waitFor(() => expect(aiProvidersApi.configure).toHaveBeenCalledWith('openai', { model: 'model-two' }));
  expect(aiProvidersApi.verify).not.toHaveBeenCalled();
  expect(await screen.findByText(/Provider settings saved/)).toBeInTheDocument();
});

test('new key stays masked and clears after saving without browser storage', async () => {
  const storage = jest.spyOn(Storage.prototype, 'setItem');
  render(<AIProviderSettings />);
  const key = await screen.findByLabelText('API key');
  expect(key).toHaveAttribute('type', 'password');
  fireEvent.change(key, { target: { value: 'synthetic-key-only' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }));
  await waitFor(() => expect(key).toHaveValue(''));
  expect(aiProvidersApi.configure).toHaveBeenCalledWith('openai', { model: 'model-one', api_key: 'synthetic-key-only' });
  expect(storage).not.toHaveBeenCalled();
  storage.mockRestore();
});

test('provider dropdown activates Claude and keeps ChatGPT UI out of API setup', async () => {
  aiProvidersApi.select.mockImplementation(async () => {
    aiProvidersApi.list.mockResolvedValue(summary({ ...openai, id: 'anthropic', label: 'Claude' }));
    return { data: {} };
  });
  render(<AIProviderSettings />);
  await screen.findByLabelText('API key');
  fireEvent.change(screen.getByLabelText('AI provider'), { target: { value: 'anthropic' } });
  await waitFor(() => expect(screen.getByLabelText('AI provider')).toHaveValue('anthropic'));
  expect(aiProvidersApi.select).toHaveBeenCalledWith('anthropic');
  expect(screen.queryByText('ChatGPT sign-in panel')).not.toBeInTheDocument();
  expect(screen.getByText(/API usage is billed separately by Anthropic/)).toBeInTheDocument();
});

test.each(['Provider quota exceeded.', { message: 'Provider quota exceeded.', code: 'quota_exceeded' }])('connection test requires an explicit click and reports provider errors: %p', async detail => {
  aiProvidersApi.verify.mockRejectedValue({ message: 'Request failed with status code 429', response: { data: { detail } } });
  render(<AIProviderSettings />);
  const button = await screen.findByRole('button', { name: 'Test connection' });
  expect(screen.getByText(/may incur API charges/)).toBeInTheDocument();
  expect(aiProvidersApi.verify).not.toHaveBeenCalled();
  fireEvent.click(button);
  expect(await screen.findByRole('alert')).toHaveTextContent('Provider quota exceeded.');
  expect(screen.queryByText(/Verified: the provider/)).not.toBeInTheDocument();
});

test('removing a credential requires confirmation and disables coaching after refresh', async () => {
  aiProvidersApi.remove.mockImplementation(async () => {
    aiProvidersApi.list.mockResolvedValue(summary({ ...openai, configured: false, key_present: false }));
    return { data: {} };
  });
  render(<AIProviderSettings />);
  fireEvent.click(await screen.findByRole('button', { name: 'Remove API key' }));
  expect(aiProvidersApi.remove).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Confirm remove key' }));
  await screen.findByText('API credential removed.');
  expect(screen.getByRole('button', { name: 'Test connection' })).toBeDisabled();
});

test('Brain status exposes active provider and navigates to settings', async () => {
  const status = jest.fn(), settings = jest.fn();
  render(<AIProviderStatus onStatus={status} onSettings={settings} />);
  expect(await screen.findByText('Configured · model-one')).toBeInTheDocument();
  expect(status).toHaveBeenLastCalledWith(openai);
  fireEvent.click(screen.getByRole('button', { name: 'AI settings' }));
  expect(settings).toHaveBeenCalledTimes(1);
});
