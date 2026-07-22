import axios from 'axios';

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

if (import.meta.env.PROD && !configuredBaseUrl) {
  throw new Error('VITE_API_BASE_URL must be configured for production builds');
}

const apiClient = axios.create({
  baseURL: configuredBaseUrl || 'http://localhost:5000/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('hrmis_access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const payload = error.response?.data || {
      success: false,
      error: {
        code: error.code === 'ECONNABORTED' ? 'REQUEST_TIMEOUT' : 'NETWORK_ERROR',
        message: error.code === 'ECONNABORTED' ? 'The request timed out' : error.message,
      },
    };
    if (error.response?.status === 401) {
      localStorage.removeItem('hrmis_access_token');
      localStorage.removeItem('hrmis_refresh_token');
    }
    return Promise.reject(payload);
  },
);

export default apiClient;
