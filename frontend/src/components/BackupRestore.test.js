import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import BackupRestore from './BackupRestore';
import { backupsApi } from '../api';

jest.mock('../api', () => ({ backupsApi: { export: jest.fn(), inspect: jest.fn(), restore: jest.fn(), recovery: jest.fn(), listRecovery: jest.fn() } }));
const preview = { format_version: 1, created_at: '2026-10-04T00:00:00Z', counts: { accounts: 2, trades: 12, diary_entries: 3 }, attachment_count: 1, warnings: [], missing_attachments: [] };
const file = new File(['synthetic archive'], 'sample.zip', { type: 'application/zip' });
beforeEach(() => {
  backupsApi.listRecovery.mockResolvedValue({ data: { backups: [] } });
  backupsApi.inspect.mockResolvedValue({ data: preview });
  backupsApi.restore.mockResolvedValue({ data: { restored: true, recovery_backup: { id: 'recovery-test' }, counts: preview.counts } });
});
async function chooseAndCheck() {
  fireEvent.change(screen.getByLabelText('Backup ZIP file'), { target: { files: [file] } });
  fireEvent.click(screen.getByRole('button', { name: 'Check backup' }));
  await screen.findByText('Backup ready to review');
}

test('restore requires inspected backup and exact confirmation before replacing journal', async () => {
  render(<BackupRestore />);
  expect(screen.queryByRole('button', { name: 'Replace journal & restore' })).not.toBeInTheDocument();
  await chooseAndCheck();
  expect(backupsApi.inspect).toHaveBeenCalledWith(file);
  const restore = screen.getByRole('button', { name: 'Replace journal & restore' });
  expect(restore).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Type RESTORE to replace the current journal'), { target: { value: 'restore' } });
  expect(restore).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Type RESTORE to replace the current journal'), { target: { value: 'RESTORE' } });
  fireEvent.click(restore);
  await screen.findByText('Journal restored');
  expect(backupsApi.restore).toHaveBeenCalledWith(file, 'RESTORE');
  expect(screen.getByRole('button', { name: 'Download previous journal' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Reload journal' })).toBeInTheDocument();
});

test('choosing a different file invalidates the inspected preview and confirmation', async () => {
  render(<BackupRestore />);
  await chooseAndCheck();
  fireEvent.change(screen.getByLabelText('Type RESTORE to replace the current journal'), { target: { value: 'RESTORE' } });
  fireEvent.change(screen.getByLabelText('Backup ZIP file'), { target: { files: [new File(['other'], 'other.zip')] } });
  expect(screen.queryByText('Backup ready to review')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Replace journal & restore' })).not.toBeInTheDocument();
  expect(backupsApi.restore).not.toHaveBeenCalled();
});

test('invalid archives expose an error and cannot be restored', async () => {
  backupsApi.inspect.mockRejectedValue({ response: { data: { detail: 'Invalid backup manifest.' } } });
  render(<BackupRestore />);
  fireEvent.change(screen.getByLabelText('Backup ZIP file'), { target: { files: [file] } });
  fireEvent.click(screen.getByRole('button', { name: 'Check backup' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid backup manifest.');
  expect(screen.queryByLabelText('Type RESTORE to replace the current journal')).not.toBeInTheDocument();
});

test('missing attachments block restore even after a successful inspection', async () => {
  backupsApi.inspect.mockResolvedValue({ data: { ...preview, missing_attachments: ['missing.png'] } });
  render(<BackupRestore />);
  await chooseAndCheck();
  expect(screen.getByText(/Restore is blocked/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Replace journal & restore' })).toBeDisabled();
  expect(screen.getByLabelText('Type RESTORE to replace the current journal')).toBeDisabled();
});

test('saved recovery copies remain discoverable when settings is opened later', async () => {
  backupsApi.listRecovery.mockResolvedValue({ data: { backups: [{ id: 'previous', created_at: '2026-10-03T00:00:00Z' }] } });
  render(<BackupRestore />);
  expect(await screen.findByText('Saved recovery copies (1)')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Saved recovery copies (1)'));
  expect(screen.getByRole('button', { name: 'Download recovery copy' })).toBeInTheDocument();
});

test('exports a ZIP only when requested and explains credential exclusions', async () => {
  URL.createObjectURL = jest.fn(() => 'blob:synthetic');
  URL.revokeObjectURL = jest.fn();
  const click = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  backupsApi.export.mockResolvedValue({ data: new Blob(['synthetic']) });
  render(<BackupRestore />);
  expect(backupsApi.export).not.toHaveBeenCalled();
  expect(screen.getByText(/API keys, sign-in tokens, and .env files are excluded/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Download backup' }));
  await waitFor(() => expect(click).toHaveBeenCalled());
  expect(await screen.findByText(/Backup download started/)).toBeInTheDocument();
  click.mockRestore();
});
