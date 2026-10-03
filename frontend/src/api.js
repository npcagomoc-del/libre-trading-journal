import axios from 'axios';

// Defaults to the local backend. REACT_APP_API_URL can point the frontend at
// another origin (a second instance, a container, a LAN machine).
export const API_BASE = (process.env.REACT_APP_API_URL ?? 'http://localhost:8010').replace(/\/+$/, '');

const api = axios.create({ baseURL: API_BASE, headers: { 'X-Journal-Request': '1' } });

export const aiApi = {
  status: () => api.get('/api/ai/status'),
  connect: (registrationId = null) => api.post('/api/ai/connect', { registration_id: registrationId }),
  models: () => api.get('/api/ai/models'),
  setModel: (slug) => api.put('/api/ai/model', { slug }),
  disconnect: () => api.post('/api/ai/disconnect'),
  verify: () => api.post('/api/ai/verify'),
};

export const accountsApi = {
  list: () => api.get('/api/accounts'),
  create: (data) => api.post('/api/accounts', data),
  update: (id, data) => api.put(`/api/accounts/${id}`, data),
};

export const tradesApi = {
  list: (params) => api.get('/api/trades', { params }),
  create: (data) => api.post('/api/trades', data),
  update: (id, data) => api.put(`/api/trades/${id}`, data),
  delete: (id) => api.delete(`/api/trades/${id}`),
  getAnalysis: (group) => api.get(`/api/trades/${encodeURIComponent(group)}/analysis`),
  getAnalysisOptions: () => api.get('/api/analysis-options'),
  updateAnalysis: (group, data) => api.patch(`/api/trades/${encodeURIComponent(group)}/analysis`, data),
  addTag: (group, data) => api.post(`/api/trades/${encodeURIComponent(group)}/tags`, data),
  deleteTag: (tagId) => api.delete(`/api/trade-tags/${tagId}`),
  setSetup: (id, setup, note) => api.patch(`/api/trades/${id}/setup`, { setup, note }),
  listCustomSetups: () => api.get('/api/setups/custom'),
  createCustomSetup: (data) => api.post('/api/setups/custom', data),
  deleteCustomSetup: (id) => api.delete(`/api/setups/custom/${id}`),
  addExecution: (id, data) => api.post(`/api/trades/${id}/executions`, data),
  updateExecution: (id, idx, data) => api.put(`/api/trades/${id}/executions/${idx}`, data),
  deleteExecution: (id, idx) => api.delete(`/api/trades/${id}/executions/${idx}`),
};

export const importApi = {
  importCsv: (formData) => api.post('/api/import-csv', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  uploadDiary: (formData) => api.post('/api/upload-diary', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
};

export const kpisApi = {
  get: (params) => api.get('/api/kpis', { params }),
};

export const diaryApi = {
  list: (params) => api.get('/api/diary', { params }),
  delete: (id) => api.delete(`/api/diary/${id}`),
  deleteByDate: (date, accountId) => api.delete(`/api/diary/by-date/${date}`, { params: accountId != null ? { account_id: accountId } : {} }),
};

export const chartApi = {
  get: (ticker, date, timeframe = '1Min', daysBack = 1, instrumentType = 'STOCK', accountId, utcOffsetHours) =>
    api.get(`/api/chart/${encodeURIComponent(ticker)}/${date}`, { params: { timeframe, days_back: daysBack, instrument_type: instrumentType, account_id: accountId, utc_offset_hours: utcOffsetHours } }),
};

export const aiProvidersApi = {
  list: () => api.get('/api/ai/providers'),
  select: (provider) => api.put('/api/ai/provider', { provider }),
  configure: (provider, config) => api.put(`/api/ai/providers/${provider}/config`, config),
  remove: (provider) => api.delete(`/api/ai/providers/${provider}/config`),
  models: (provider) => api.get(`/api/ai/providers/${provider}/models`),
  verify: (provider) => api.post(`/api/ai/providers/${provider}/verify`),
};

export const backupsApi = {
  listRecovery: () => api.get('/api/backups/recovery'),
  export: () => api.post('/api/backups/export', null, { responseType: 'blob' }),
  inspect: (file) => {
    const data = new FormData();
    data.append('file', file);
    return api.post('/api/backups/inspect', data);
  },
  restore: (file, confirmation) => {
    const data = new FormData();
    data.append('file', file);
    data.append('confirmation', confirmation);
    return api.post('/api/backups/restore', data);
  },
  recovery: (id) => api.get(`/api/backups/recovery/${encodeURIComponent(id)}`, { responseType: 'blob' }),
};

export const marketDataApi = {
  status: (id) => api.get(`/api/market-data/${id}`),
  connect: (id, data) => api.post(`/api/market-data/${id}/connect`, data),
  disconnect: (id) => api.delete(`/api/market-data/${id}`),
};

export const insightsApi = {
  get: (params) => api.get('/api/insights', { params }),
};

export const calendarApi = {
  get: (params) => api.get('/api/calendar', { params }),
};

export const brainApi = {
  chat: (messages, accountId) =>
    api.post('/api/brain', { messages, account_id: accountId }),
};

export const dailySummaryApi = {
  get: (params) => api.get('/api/daily-summary', { params }),
};

export const goalsApi = {
  get: (params) => api.get('/api/goals', { params }),
  put: (data) => api.put('/api/goals', data),
};

export const reportsApi = {
  get: (params) => api.get('/api/reports', { params }),
};

// Settings > Library: strategy names, sources and tags. `item` is
// { kind: 'strategy' | 'source' | 'tag', tag_type?, name, ... }.
export const libraryApi = {
  list: () => api.get('/api/library'),
  create: (item) => api.post('/api/library', item),
  update: (item) => api.put('/api/library', item),
  merge: (item) => api.post('/api/library/merge', item),
  remove: (item) => api.post('/api/library/delete', item),
};

export const edgeReportApi = {
  get: (params) => api.get('/api/edge-report', { params }),
};

export const weeklySummaryApi = {
  get: (params) => api.get('/api/weekly-summary', { params }),
};

export const yearlyKpisApi = {
  get: (params) => api.get('/api/yearly-kpis', { params }),
};
