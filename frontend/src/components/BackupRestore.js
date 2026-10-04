import { useCallback, useEffect, useState } from 'react';
import { Archive, Download, Upload, ShieldCheck } from 'lucide-react';
import { backupsApi } from '../api';
import './journal-settings.css';

async function errorText(e) {
  let data = e?.response?.data;
  if (data instanceof Blob) { try { data = JSON.parse(await data.text()); } catch (_) { data = null; } }
  return typeof data?.detail === 'string' ? data.detail : e?.message || 'The backup operation failed. Please try again.';
}

function downloadArchive(response, fallback) {
  const blob = response.data instanceof Blob ? response.data : new Blob([response.data], { type: 'application/zip' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fallback;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function BackupRestore() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [restored, setRestored] = useState(null);
  const [recoveryCopies, setRecoveryCopies] = useState([]);
  const [recoveryError, setRecoveryError] = useState('');
  const refreshRecovery = useCallback(async () => {
    try { const result = await backupsApi.listRecovery(); setRecoveryCopies(result.data.backups || []); setRecoveryError(''); }
    catch (_) { setRecoveryError('Saved recovery copies could not be loaded.'); }
  }, []);
  useEffect(() => { refreshRecovery(); }, [refreshRecovery]);
  const run = async (operation, action) => {
    setBusy(operation); setError(''); setNotice('');
    try { await action(); }
    catch (e) { setError(await errorText(e)); }
    finally { setBusy(''); }
  };
  const exportBackup = () => run('export', async () => {
    downloadArchive(await backupsApi.export(), `libre-trading-journal-${new Date().toISOString().slice(0, 10)}.zip`);
    setNotice('Backup download started. Keep a copy in a safe location.');
  });
  const inspect = () => run('inspect', async () => {
    setPreview(null); setConfirmation('');
    const result = await backupsApi.inspect(file);
    setPreview(result.data);
  });
  const restore = () => {
    if (!preview || !file || confirmation !== 'RESTORE' || busy || preview.missing_attachments?.length) return;
    run('restore', async () => {
      const result = await backupsApi.restore(file, confirmation);
      if (!result.data?.restored) throw new Error('The server did not confirm the restore. Check the journal before trying again.');
      setRestored(result.data); setPreview(null); setConfirmation('');
      await refreshRecovery();
    });
  };
  return <section className="card journal-connection" aria-labelledby="backup-title">
    <div className="connection-heading"><div className="connection-icon"><Archive size={20} aria-hidden="true" /></div><div><h2 className="section-title" id="backup-title">Backup &amp; restore</h2><p className="connection-copy">Save or restore all journal accounts and attachments.</p></div></div>
    <div className="backup-columns">
      <div className="backup-export"><h3>Download your journal</h3><p className="connection-copy">A ZIP archive of all accounts, trades, diary entries, and their attachments. Backups contain private trading data.</p><ol className="settings-steps">
        <li>Finish any imports or AI analysis, then click <b>Download backup</b>.</li>
        <li>Find the ZIP in your browser’s downloads and keep a copy in a safe location.</li>
        <li>Select that ZIP under <b>Restore a backup</b> and click <b>Check backup</b> to review its contents. Checking does not replace your journal.</li>
      </ol><button type="button" className="btn btn-primary" disabled={!!busy || !!restored} onClick={exportBackup}><Download size={15} aria-hidden="true" />{busy === 'export' ? 'Preparing backup…' : 'Download backup'}</button><p className="connection-hint"><ShieldCheck size={14} aria-hidden="true" /> API keys, sign-in tokens, and .env files are excluded. Reconnect services after moving to a new machine.</p></div>
      <div className="backup-import"><h3>Restore a backup</h3><p className="connection-copy">Restoring replaces this entire journal, including every account. A recovery backup of the current journal is saved first.</p><ol className="settings-steps">
        <li>Finish work in other journal tabs and download a current backup.</li>
        <li>Choose your saved ZIP below, then click <b>Check backup</b>.</li>
        <li>Review its date, record counts, and any warnings. Type <b>RESTORE</b> and click <b>Replace journal &amp; restore</b>.</li>
        <li>Wait for confirmation, then click <b>Reload journal</b>. Reload any other open journal tabs too.</li>
      </ol><label htmlFor="journal-backup-file"><span className="field-label">Backup ZIP file</span><input id="journal-backup-file" type="file" accept=".zip,application/zip" disabled={!!busy || !!restored} onChange={e => { setFile(e.target.files?.[0] || null); setPreview(null); setConfirmation(''); setError(''); setNotice(''); }} /></label><button type="button" className="btn btn-ghost" disabled={!file || !!busy || !!restored} onClick={inspect}><Upload size={15} aria-hidden="true" />{busy === 'inspect' ? 'Checking backup…' : 'Check backup'}</button></div>
    </div>
    {preview && <div className="backup-preview"><div className="backup-preview-heading"><strong>Backup ready to review</strong><span className="connection-hint">Created {preview.created_at ? new Date(preview.created_at).toLocaleString() : 'date unavailable'} · Format {preview.format_version}</span></div><dl className="backup-counts">{[['Accounts', preview.counts?.accounts], ['Trades', preview.counts?.trades], ['Diary entries', preview.counts?.diary_entries], ['Attachments', preview.attachment_count]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value ?? '—'}</dd></div>)}</dl>
      {!!preview.warnings?.length && <div className="connection-callout" role="status"><strong>Review before restoring</strong><ul>{preview.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul></div>}
      {!!preview.missing_attachments?.length && <p className="connection-callout">This backup is missing {preview.missing_attachments.length} referenced attachment(s). Restore is blocked. Create a complete backup with those files included, then check it again.</p>}
      <div className="backup-confirm"><label htmlFor="restore-confirmation"><span className="field-label">Type RESTORE to replace the current journal</span><input id="restore-confirmation" value={confirmation} autoComplete="off" spellCheck={false} disabled={!!busy || !!preview.missing_attachments?.length} onChange={e => setConfirmation(e.target.value)} placeholder="RESTORE" /></label><button type="button" className="btn btn-danger" disabled={!!busy || confirmation !== 'RESTORE' || !!preview.missing_attachments?.length} onClick={restore}>{busy === 'restore' ? 'Restoring journal…' : 'Replace journal & restore'}</button></div>
    </div>}
    {restored && <div className="backup-success" role="status"><strong>Journal restored</strong><p>Reload the app to load the restored accounts and records.{restored.restart_required ? ' Restart the backend before reloading.' : ''} A recovery copy of your previous journal was saved locally.</p><div className="connection-actions"><button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>Reload journal</button>{restored.recovery_backup?.id && <button type="button" className="btn btn-ghost" disabled={!!busy} onClick={() => run('recovery', async () => { downloadArchive(await backupsApi.recovery(restored.recovery_backup.id), 'libre-journal-before-restore.zip'); setNotice('Recovery backup download started.'); })}>{busy === 'recovery' ? 'Downloading…' : 'Download previous journal'}</button>}</div></div>}
    <details className="backup-recovery"><summary>Saved recovery copies {recoveryCopies.length ? `(${recoveryCopies.length})` : ''}</summary><p className="connection-hint">These automatic snapshots preserve the journal from before a restore. Download one, then choose it above to inspect and restore it.</p>{recoveryError ? <p className="connection-hint" role="status">{recoveryError} <button type="button" className="btn btn-ghost btn-sm" onClick={refreshRecovery}>Retry recovery list</button></p> : recoveryCopies.length ? <ul>{recoveryCopies.map(copy => <li key={copy.id}><span>{copy.created_at ? new Date(copy.created_at).toLocaleString() : copy.id}</span><button type="button" className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => run('recovery', async () => { downloadArchive(await backupsApi.recovery(copy.id), `libre-recovery-${copy.id}.zip`); setNotice('Recovery backup download started.'); })}>Download recovery copy</button></li>)}</ul> : <p className="connection-hint">No recovery copies saved yet.</p>}</details>
    {notice && <div className="connection-message" role="status">{notice}</div>}
    {error && <div className="notice neg" role="alert">{error}</div>}
  </section>;
}
