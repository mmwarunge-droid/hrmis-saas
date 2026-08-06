import apiClient from './apiClient';

export const goalApi = {
  list: (params = {}) => apiClient.get('/goals', { params }),
  summary: () => apiClient.get('/goals/summary'),
  get: (id) => apiClient.get(`/goals/${id}`),
  create: (payload) => apiClient.post('/goals', payload),
  update: (id, payload) => apiClient.patch(`/goals/${id}`, payload),
  checkIn: (id, payload) => apiClient.post(`/goals/${id}/check-ins`, payload),
};
