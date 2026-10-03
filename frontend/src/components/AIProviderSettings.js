import { useCallback, useEffect, useState } from 'react';
import { Brain, KeyRound, RefreshCw } from 'lucide-react';
import { aiProvidersApi } from '../api';
import ChatGPTConnection from './ChatGPTConnection';
import './journal-settings.css';

const LABELS = { chatgpt: 'ChatGPT sign-in', openai: 'OpenAI API key (ChatGPT API)', anthropic: 'Claude API key', openrouter: 'OpenRouter API key' };
const errorText = e => {
  const detail = e?.response?.data?.detail;
  return typeof detail === 'string' ? detail : typeof detail?.message === 'string' ? detail.message : e?.message || 'Could not update AI settings. Please try again.';
};

function useProviders() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const refresh = useCallback(async () => {
    try {
      const result = await aiProvidersApi.list();
      setData(result.data); setError('');
      return result.data;
    } catch (e) { setError(errorText(e)); return null; }
  }, []);
  useEffect(() => {
    refresh();
    window.addEventListener('focus', refresh);
    window.addEventListener('journal-ai-changed', refresh);
    return () => {
      window.removeEventListener('focus', refresh);
      window.removeEventListener('journal-ai-changed', refresh);
    };
  }, [refresh]);
  return { data, error, refresh };
}

export function AIProviderStatus({ onStatus, onSettings }) {
  const { data, error, refresh } = useProviders();
  const provider = data?.providers?.find(p => p.id === data.active_provider);
  useEffect(() => { onStatus?.(error ? null : provider || null); }, [provider, error, onStatus]);
  return <div className="coach-connection-strip">
    <div>
      <strong>{provider ? LABELS[provider.id] || provider.label : 'AI coach'}</strong>
      <div className="connection-copy">{error ? 'Connection status unavailable.' : !data ? 'Checking connection…' : provider?.configured ? `Configured${provider.model ? ` · ${provider.model}` : ''}` : 'Choose a provider and connect in Settings.'}</div>
    </div>
    {onSettings && <button type="button" className="btn btn-ghost btn-sm" onClick={onSettings}>AI settings</button>}
    {error && <button type="button" className="btn btn-ghost btn-sm" onClick={refresh}>Retry</button>}
  </div>;
}

function APIKeyForm({ provider, onChanged }) {
  const [key, setKey] = useState('');
  const [model, setModel] = useState(provider.model || '');
  const [models, setModels] = useState([]);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [removePrompt, setRemovePrompt] = useState(false);
  const dirty = !!key.trim() || model.trim() !== (provider.model || '');
  const run = async (action, operation, message) => {
    setBusy(operation); setError(''); setNotice('');
    try {
      const result = await action();
      setNotice(message || result.data?.response || 'Saved.');
      if (operation === 'save' || operation === 'remove') { setKey(''); setRemovePrompt(false); }
      if (operation !== 'models') await onChanged();
      window.dispatchEvent(new Event('journal-ai-changed'));
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(''); }
  };
  return <div className="provider-form">
    <p className="connection-copy">API usage is billed separately by {provider.id === 'anthropic' ? 'Anthropic' : provider.id === 'openrouter' ? 'OpenRouter and its model providers' : 'OpenAI'}. A ChatGPT or Claude subscription does not include this API usage. Coaching sends relevant trades, notes, and supported diary images to the selected provider.</p>
    <div className="connection-fields">
      <div><label htmlFor="provider-api-key"><span className="field-label">API key</span></label>
        <input id="provider-api-key" type="password" autoComplete="new-password" spellCheck={false} value={key} disabled={!!busy}
          onChange={e => setKey(e.target.value)} placeholder={provider.key_present ? 'Saved key · leave blank to keep it' : 'Paste your API key'} aria-describedby="provider-key-help" />
        <span id="provider-key-help" className="connection-hint">{provider.key_present ? 'A key is stored locally. Leave this field blank to keep it.' : 'Stored by the local backend, never in browser storage.'}{provider.credential_storage ? ` ${provider.credential_storage}` : ''}</span>
      </div>
      <div><label htmlFor="provider-model"><span className="field-label">Model ID</span></label>
        <input id="provider-model" list="provider-models" value={model} disabled={!!busy} onChange={e => setModel(e.target.value)} placeholder="Choose or enter a model ID" aria-describedby="provider-model-help" />
        <datalist id="provider-models">{models.map(m => <option key={m.slug} value={m.slug}>{m.display_name || m.slug}</option>)}</datalist>
        <span id="provider-model-help" className="connection-hint">Enter the exact model ID, or refresh models to see available suggestions.</span>
      </div>
    </div>
    <div className="connection-actions">
      <button type="button" className="btn btn-primary btn-sm" disabled={!!busy || !model.trim() || (!provider.key_present && !key.trim())}
        onClick={() => run(() => aiProvidersApi.configure(provider.id, { model: model.trim(), ...(key.trim() ? { api_key: key.trim() } : {}) }), 'save', 'Provider settings saved. Test the connection to check access.')}>{busy === 'save' ? 'Saving…' : 'Save settings'}</button>
      <button type="button" className="btn btn-ghost btn-sm" disabled={!!busy || !provider.configured || dirty} aria-describedby="provider-test-help"
        onClick={() => run(() => aiProvidersApi.verify(provider.id), 'test', 'Verified: the provider completed a test response.')}>{busy === 'test' ? 'Testing…' : 'Test connection'}</button>
      <button type="button" className="btn btn-ghost btn-sm" disabled={!!busy || !provider.key_present}
        onClick={() => run(async () => { const result = await aiProvidersApi.models(provider.id); setModels(result.data.models || []); return result; }, 'models', 'Model suggestions refreshed. You can also enter a model ID manually.')}><RefreshCw size={14} aria-hidden="true" />{busy === 'models' ? 'Refreshing…' : 'Refresh models'}</button>
      {provider.key_present && <button type="button" className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => setRemovePrompt(v => !v)}>Remove API key</button>}
    </div>
    <p id="provider-test-help" className="connection-hint">Test connection sends a small request and may incur API charges. Save changes before testing. Saving a key does not verify access.</p>
    {provider.message && <p className="connection-hint">{provider.message}</p>}
    {removePrompt && <div className="connection-callout"><p>Remove this provider’s stored credential? Coaching with this provider will stop until you add a key again.</p><div className="connection-actions"><button type="button" className="btn btn-danger btn-sm" disabled={!!busy} onClick={() => run(() => aiProvidersApi.remove(provider.id), 'remove', 'API credential removed.')}>Confirm remove key</button><button type="button" className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => setRemovePrompt(false)}>Cancel</button></div></div>}
    {notice && <div className="connection-message" role="status">{notice}</div>}
    {error && <div className="notice neg" role="alert">{error}</div>}
  </div>;
}

export default function AIProviderSettings() {
  const { data, error: loadError, refresh } = useProviders();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const selected = data?.providers?.find(p => p.id === data.active_provider);
  const choose = async value => {
    setBusy(true); setError('');
    try { await aiProvidersApi.select(value); await refresh(); window.dispatchEvent(new Event('journal-ai-changed')); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  };
  return <section className="card journal-connection" aria-labelledby="ai-provider-title" id="ai-provider-settings">
    <div className="connection-heading"><div className="connection-icon"><Brain size={20} aria-hidden="true" /></div><div><div className="connection-eyebrow">OPTIONAL COACHING</div><h2 className="section-title" id="ai-provider-title">Your AI, your choice</h2><p className="connection-copy">One provider for Brain, diary analysis, and trading reviews.</p></div></div>
    <div className="provider-selection"><label htmlFor="ai-provider"><span className="field-label">AI provider</span><select id="ai-provider" value={data?.active_provider || 'chatgpt'} disabled={busy || !data} onChange={e => choose(e.target.value)}>{Object.entries(LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      {selected && <div className="connection-badges" aria-label="Provider status"><span className="connection-badge active">Active provider</span><span className="connection-badge"><KeyRound size={12} aria-hidden="true" />{selected.configured ? 'Configured' : 'Setup needed'}</span><span className="connection-badge">{selected.supports_images === true ? 'Images supported' : selected.supports_images === false ? 'Text only' : 'Image support unknown'}</span></div>}
    </div>
    {!data && !loadError && <p role="status" className="connection-copy">Loading providers…</p>}
    {(loadError || error) && <div className="notice neg" role="alert">{loadError || error} <button type="button" className="btn btn-ghost btn-sm" onClick={refresh}>Retry</button></div>}
    {selected?.id === 'chatgpt' ? <div className="provider-chatgpt"><ChatGPTConnection onStatus={refresh} /></div> : selected && <APIKeyForm key={selected.id} provider={selected} onChanged={refresh} />}
  </section>;
}
