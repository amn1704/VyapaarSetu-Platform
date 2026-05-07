const rawBaseUrl = import.meta.env.VITE_API_BASE_URL;

// Production-safe default uses same-origin '/api' routing.
// Set VITE_API_BASE_URL when frontend and backend are on different hosts.
export const API_BASE_URL = (rawBaseUrl || '').replace(/\/+$/, '');

export function apiUrl(path) {
  if (!path) return API_BASE_URL;
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  if (!path.startsWith('/')) return API_BASE_URL ? `${API_BASE_URL}/${path}` : `/${path}`;
  return API_BASE_URL ? `${API_BASE_URL}${path}` : path;
}

