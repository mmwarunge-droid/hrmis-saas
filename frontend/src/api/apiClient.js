import axios from 'axios';

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

if (import.meta.env.PROD && !configuredBaseUrl) {
  throw new Error('VITE_API_BASE_URL must be configured for production builds');
}

const MUTATING_METHODS = new Set(['post', 'put', 'patch', 'delete']);

function readCookie(name) {
  const prefix = `${encodeURIComponent(name)}=`;
  const cookie = document.cookie
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));

  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

const apiClient = axios.create({
  baseURL: configuredBaseUrl || 'http://localhost:5000/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  const method = config.method?.toLowerCase();
  if (!MUTATING_METHODS.has(method)) return config;

  const isRefreshRequest = config.url?.includes('/auth/refresh');
  const csrfCookieName = isRefreshRequest ? 'csrf_refresh_token' : 'csrf_access_token';
  const csrfToken = readCookie(csrfCookieName);

  if (csrfToken) {
    config.headers.set('X-CSRF-TOKEN', csrfToken);
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const payload = error.response?.data || {
      success: false,
      error: {
        code: error.code === 'ECONNABORTED' ? 'REQUEST_TIMEOUT' : 'NETWORK_ERROR',
        message: error.code === 'ECONNABORTED' ? 'The request timed out' : error.message,
      },
    };
    return Promise.reject(payload);
  },
);

export default apiClient;
