import apiClient from './apiClient';

export const authApi = {
  login: (payload) => apiClient.post('/auth/login', payload),
  me: () => apiClient.get('/auth/me'),
  refresh: () => apiClient.post('/auth/refresh'),
  register: (payload) => apiClient.post('/auth/register', payload),
  sessions: () => apiClient.get('/auth/sessions'),
  revokeSession: (sessionId) => apiClient.delete(`/auth/sessions/${sessionId}`),
  logoutAll: () => apiClient.post('/auth/logout-all'),
  logout: () => apiClient.post('/auth/logout'),
};
