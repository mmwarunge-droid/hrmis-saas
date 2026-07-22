import apiClient from './apiClient';

export const authApi = {
  login: (payload) => apiClient.post('/auth/login', payload),
  me: () => apiClient.get('/auth/me'),
  register: (payload) => apiClient.post('/auth/register', payload),
  logout: () => apiClient.post('/auth/logout'),
};
