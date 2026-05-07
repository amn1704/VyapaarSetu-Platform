import { apiUrl } from '../config/env';

function toQueryString(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : '';
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

async function readJson(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // Handle Pydantic v2 validation errors (array of error objects)
    let message = data?.detail || data?.message || `Request failed (${res.status})`;
    if (Array.isArray(message)) {
      message = message.map(e => e.msg || JSON.stringify(e)).join(', ');
    } else if (typeof message === 'object') {
      message = JSON.stringify(message);
    }
    const err = new Error(message);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  get: async (path, { params, timeoutMs } = {}) => {
    const res = await fetchWithTimeout(apiUrl(`${path}${toQueryString(params)}`), {}, timeoutMs);
    return readJson(res);
  },
  post: async (path, body, { timeoutMs } = {}) => {
    const res = await fetchWithTimeout(apiUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {}),
    }, timeoutMs);
    return readJson(res);
  },
};

