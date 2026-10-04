import { useEffect, useState } from 'react';
import { Cable } from 'lucide-react';
import { marketDataApi } from '../api';
import './journal-settings.css';

const errorText = e => e?.response?.data?.detail || e?.message || 'Connection failed';
const defaults = { transport: 'mcp', broker: 'fundednext', path: '', utc_offset_hours: 0, test_symbol: 'XAUUSD', mcp_url: 'http://127.0.0.1:22346/mcp', server_utc_offset_hours: 3 };

export default function MarketDataConnection({ accounts, accountId }) {
  const [selected, setSelected] = useState(accountId || accounts[0]?.id || '');
  const [config, setConfig] = useState(null);
  const [paths, setPaths] = useState([]);
  const [draft, setDraft] = useState(defaults);
  const [accessKey, setAccessKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    if (accountId != null) setSelected(accountId);
  }, [accountId]);

  useEffect(() => {
    if (!accounts.some(a => a.id === selected)) setSelected(accounts[0]?.id || '');
  }, [accounts, selected]);

  useEffect(() => {
    let cancelled = false;
    setError(''); setNotice(''); setConfig(null); setAccessKey(''); setLoading(true);
    if (!selected) { setLoading(false); return; }
    marketDataApi.status(selected).then(({ data }) => {
      if (cancelled) return;
      setConfig(data.config); setPaths(data.installations || []);
      setDraft(data.config ? { ...defaults,
        broker: data.config.broker, path: data.config.path,
        utc_offset_hours: data.config.utc_offset_hours, test_symbol: data.config.test_symbol,
        transport: data.config.transport || 'terminal', mcp_url: data.config.mcp_url || defaults.mcp_url,
        server_utc_offset_hours: data.config.server_utc_offset_hours ?? 3,
      } : { ...defaults, path: data.installations?.[0] || '' });
    }).catch(e => { if (!cancelled) setError(errorText(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selected]);

  const change = (name, value) => { setError(''); setNotice(''); setDraft(d => ({ ...d, [name]: value })); };
  const run = async disconnect => {
    setBusy(true); setError(''); setNotice('');
    try {
      const payload = draft.transport === 'mcp' ? { ...draft, mcp_api_key: accessKey || undefined } : draft;
      const { data } = await (disconnect ? marketDataApi.disconnect(selected) : marketDataApi.connect(selected, payload));
      setConfig(disconnect ? null : data.config);
      setAccessKey('');
      setNotice(disconnect ? 'Market-data connection removed from this journal account.' : data.message);
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  };

  return (
    <section className="card" aria-label="MT5 market data" style={{ marginBottom: 'var(--space-5)' }}>
      <h2 className="section-title"><Cable size={19} aria-hidden="true" /> Market data · MT5</h2>
      <p className="section-sub">Use prices from your MT5 desktop terminal for trade charts.</p>
      <div className="settings-guide" aria-labelledby="mt5-guide-title">
        <h3 id="mt5-guide-title">Set up trade charts</h3>
        <p className="connection-copy"><strong>Keep MT5 open and signed in while loading charts.</strong> You can minimize it. MT5 is not needed for reviewing journal records without charts.</p>
        <ol className="settings-steps">
          <li><strong>Open MT5 on this computer.</strong> Sign in to the broker account you want to use for prices. Wait until MT5 is connected.</li>
          <li><strong>Choose the connection method below.</strong> {draft.transport === 'mcp' ? <>In MT5, go to <b>Tools → Options → MCP</b> and enable the internal server. Copy its local address and access key into the matching fields below. If your MT5 has no MCP tab, select <b>MT5 Python · desktop terminal</b>.</> : <>Select your MT5 installation below, or leave the terminal field blank to auto-detect it. No MCP access key is needed.</>}</li>
          <li><strong>Match your account and clocks.</strong> Choose the journal account and the broker supplying prices. Use the exact symbol shown in MT5 Market Watch, including any suffix. For Exness app history, set the trade timestamp clock to <b>UTC+0</b>.{draft.transport === 'mcp' && ' Set the MT5 server clock to the price provider’s clock on the trade date.'}</li>
          <li><strong>Connect, then open a trade.</strong> Click <b>Connect &amp; test MT5</b>. Once test candles are returned, open a forex, gold, or supported crypto trade in <b>Trade View</b> to see its chart.</li>
        </ol>
        <details className="settings-details mt5-walkthrough">
          <summary>Watch MT5 walkthrough</summary>
          <video controls preload="none" poster="/tutorials/mt5-setup.jpg" aria-label="MT5 chart setup walkthrough">
            <source src="/tutorials/mt5-charts-guide.mp4" type="video/mp4" />
            <track kind="captions" src="/tutorials/mt5-charts-guide.en.vtt" srcLang="en" label="English" />
            Your browser does not support this video. Follow the steps above.
          </video>
        </details>
      </div>
      {!accounts.length ? <div role="status">Create a journal account first.</div> : <>
        <div className="form-grid">
          <div className="form-group"><label htmlFor="mt5-connection">Connection method</label>
            <select id="mt5-connection" value={draft.transport} disabled={busy || loading} onChange={e => change('transport', e.target.value)}>
              <option value="mcp">MT5 MCP · built-in server</option><option value="terminal">MT5 Python · desktop terminal</option>
            </select>
          </div>
          <div className="form-group"><label htmlFor="mt5-journal">Journal account</label>
            <select id="mt5-journal" value={selected} disabled={busy} onChange={e => setSelected(Number(e.target.value))}>
              {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
          <div className="form-group"><label htmlFor="mt5-provider">MT5 price provider</label>
            <select id="mt5-provider" value={draft.broker} disabled={busy || loading} onChange={e => change('broker', e.target.value)}>
              <option value="fundednext">FundedNext</option><option value="ftmo">FTMO</option><option value="exness">Exness</option>
            </select>
          </div>
          {draft.transport === 'mcp' ? <>
            <div className="form-group"><label htmlFor="mt5-mcp-url">Local MCP address</label>
              <input id="mt5-mcp-url" value={draft.mcp_url} disabled={busy || loading} onChange={e => change('mcp_url', e.target.value)} />
            </div>
            <div className="form-group"><label htmlFor="mt5-mcp-key">MT5 MCP access key</label>
              <input id="mt5-mcp-key" type="password" autoComplete="off" value={accessKey} disabled={busy || loading} onChange={e => { setAccessKey(e.target.value); setError(''); }} placeholder={config?.has_key ? 'Saved securely · leave blank to reuse' : 'From Tools → Options → MCP in MT5'} />
            </div>
            <div className="form-group"><label htmlFor="mt5-server-clock">MT5 server clock for these dates</label>
              <select id="mt5-server-clock" value={draft.server_utc_offset_hours} disabled={busy || loading} onChange={e => change('server_utc_offset_hours', Number(e.target.value))}>
                <option value={3}>UTC+3 · FundedNext / FTMO daylight time</option><option value={2}>UTC+2 · FundedNext / FTMO standard time</option><option value={0}>UTC+0 · Exness</option>
                {![0, 2, 3].includes(draft.server_utc_offset_hours) && <option value={draft.server_utc_offset_hours}>UTC{draft.server_utc_offset_hours >= 0 ? '+' : ''}{draft.server_utc_offset_hours}</option>}
              </select>
            </div>
          </> : <div className="form-group"><label htmlFor="mt5-path">MT5 terminal</label>
            <input id="mt5-path" list="mt5-installations" value={draft.path} disabled={busy || loading} onChange={e => change('path', e.target.value)} placeholder="Auto-detect, or path to terminal64.exe" />
            <datalist id="mt5-installations">{paths.map(p => <option key={p} value={p} />)}</datalist>
          </div>}
          <div className="form-group"><label htmlFor="mt5-symbol">Symbol to test</label>
            <input id="mt5-symbol" value={draft.test_symbol} maxLength={64} disabled={busy || loading} onChange={e => change('test_symbol', e.target.value.trim())} placeholder="XAUUSD" />
          </div>
          <div className="form-group"><label htmlFor="mt5-clock">Trade timestamp clock</label>
            <select id="mt5-clock" value={draft.utc_offset_hours} disabled={busy || loading} onChange={e => change('utc_offset_hours', Number(e.target.value))}>
              <option value={0}>UTC+0 · Exness history</option>
              <option value={2}>UTC+2 · FTMO standard time</option>
              <option value={3}>UTC+3 · FTMO daylight time</option>
              <option value={8}>UTC+8 · Philippine local time</option>
              {![0, 2, 3, 8].includes(draft.utc_offset_hours) && <option value={draft.utc_offset_hours}>UTC{draft.utc_offset_hours >= 0 ? '+' : ''}{draft.utc_offset_hours}</option>}
            </select>
          </div>
        </div>
        <details className="settings-details"><summary>About access and chart clocks</summary>
          <p className="connection-copy">This connection only reads account details and prices; it cannot place trades. MCP access keys are saved encrypted on this computer.</p>
          <p className="connection-copy">Trade timestamps and the price provider may use different clocks. Exness imports use UTC+0 automatically. For FTMO or FundedNext, confirm whether the historical date used UTC+2 or UTC+3.</p>
        </details>
        {config && <p role="status">Saved feed: {config.broker.toUpperCase()} · {config.server} · {config.account_label}</p>}
        {draft.broker !== 'exness' && <p className="text-muted" style={{ fontSize: 13 }}>These prices are a reference for Exness trades; broker quotes and candle shapes may differ.</p>}
        {error && <div className="notice neg" role="alert">{error}</div>}
        {notice && <div className="notice" role="status">{notice}</div>}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 12 }}>
          <button className="btn btn-primary" type="button" disabled={busy || loading || !draft.test_symbol} onClick={() => run(false)}>{busy ? 'Checking MT5…' : 'Connect & test MT5'}</button>
          {config && <button className="btn btn-secondary" type="button" disabled={busy || loading} onClick={() => run(true)}>Disconnect market data</button>}
        </div>
      </>}
    </section>
  );
}
