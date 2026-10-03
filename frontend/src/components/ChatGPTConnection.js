import { useCallback, useEffect, useState } from 'react';
import { aiApi, API_BASE } from '../api';

const USAGE_URL = 'https://chatgpt.com/settings/usage';
const errText = e => e?.response?.data?.detail || e?.message || 'Could not connect to ChatGPT.';

export default function ChatGPTConnection({ compact = false, onStatus }) {
  const [status, setStatus] = useState(null);
  const [models, setModels] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const refresh = useCallback(async () => {
    try {
      const result = await aiApi.status();
      setStatus(result.data);
      onStatus?.(result.data);
      return result.data;
    } catch (e) { setError(errText(e)); }
  }, [onStatus]);

  useEffect(() => {
    refresh();
    const focus = () => refresh();
    window.addEventListener('focus', focus);
    return () => window.removeEventListener('focus', focus);
  }, [refresh]);

  const fetchModels = useCallback(async () => {
    try {
      const result = await aiApi.models();
      setModels(result.data.models);
      await refresh();
    } catch (e) { setError(errText(e)); }
  }, [refresh]);

  useEffect(() => {
    if (status?.plan_usage_enabled && !compact) fetchModels();
  }, [status?.active_registration, status?.plan_usage_enabled, compact, fetchModels]);

  const connect = async (registrationId = null) => {
    // Open synchronously from the user's click so popup blockers do not swallow sign-in.
    const signIn = window.open('about:blank', '_blank');
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await aiApi.connect(registrationId);
      const url = API_BASE + result.data.start_path;
      if (signIn) { signIn.opener = null; signIn.location.href = url; }
      else { window.location.assign(url); }
      setNotice('Complete sign-in in the new tab, then return here.');
    } catch (e) { signIn?.close(); setError(errText(e)); }
    finally { setBusy(false); }
  };

  const run = async (action) => {
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await action();
      setNotice(result.data.response || result.data.message || 'Saved.');
      await refresh();
      window.dispatchEvent(new Event('journal-ai-changed'));
    } catch (e) { setError(errText(e)); }
    finally { setBusy(false); }
  };

  const ready = status?.connected && status?.plan_usage_enabled;
  return (
    <section className={compact ? undefined : 'card'} aria-label="ChatGPT connection"
      style={compact ? { padding: '10px 16px', borderBottom: '1px solid var(--divider)' } : { padding: 20, marginBottom: 24 }}>
      {!compact && <h2 className="section-title" style={{ marginBottom: 8 }}>AI coach · ChatGPT</h2>}
      <div style={{ fontSize: compact ? 12 : 14, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
        {ready ? `Using your ChatGPT plan${status.model ? ` · ${status.model}` : ''}` : 'Connect your ChatGPT account to use Brain and AI coaching.'}
      </div>
      {!compact && <p style={{ fontSize: 14, lineHeight: 1.6 }}>
        Uses your existing eligible ChatGPT plan. Coaching requests send the relevant trade history, notes, and any diary images to OpenAI.
        There is no API-key billing fallback. In ChatGPT Usage settings, leave <strong>Allow apps to use credits after reaching your usage limit</strong> disabled to avoid spending purchased credits.
      </p>}
      {status?.connected && !status.plan_usage_enabled && <p role="status">Sign-in is connected, but permission to use your ChatGPT plan was not granted. Reconnect to enable it.</p>}
      {!compact && ready && <label style={{ display: 'block', margin: '12px 0', maxWidth: 480 }}>
        <span className="field-label">Coach model</span>
        <select aria-label="Coach model" value={status.model || ''} disabled={busy || !models.length}
          onChange={e => run(() => aiApi.setModel(e.target.value))}>
          {!models.length && <option value="">Loading available models…</option>}
          {models.map(model => <option key={model.slug} value={model.slug}>{model.display_name}</option>)}
        </select>
      </label>}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10, alignItems: 'center' }}>
        {!ready && <button type="button" className="btn btn-primary btn-sm" disabled={busy}
          onClick={() => connect(status?.active_registration)}>Continue with ChatGPT</button>}
        {!compact && ready && <>
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => run(aiApi.verify)}>
            {busy ? 'Working…' : 'Test connection'}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => run(aiApi.disconnect)}>Disconnect</button>
          <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={fetchModels}>Refresh models</button>
        </>}
        {!compact && <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => connect()}>Use another ChatGPT account</button>}
        {!compact && status?.registrations?.filter(reg => reg.id !== status.active_registration).map(reg => (
          <button type="button" key={reg.id} className="btn btn-ghost btn-sm" disabled={busy} onClick={() => connect(reg.id)}>
            Connect {reg.label} · {reg.id.slice(0, 6)}
          </button>
        ))}
        <a href={USAGE_URL} target="_blank" rel="noreferrer" style={{ fontSize: 13 }}>Manage ChatGPT usage</a>
        {!compact && <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={refresh}>Check connection</button>}
      </div>
      {!compact && ready && <div role="status" style={{ fontSize: 13, marginTop: 10, color: 'var(--text-secondary)' }}>
        {status.verification === 'completed' ? 'Verified: ChatGPT completed a response.' : 'Signed in. Test the connection to verify account access.'}
      </div>}
      {notice && <div role="status" style={{ marginTop: 10, fontSize: 13 }}>{notice}</div>}
      {error && <div role="alert" className="notice neg" style={{ marginTop: 10 }}>{error}</div>}
    </section>
  );
}
