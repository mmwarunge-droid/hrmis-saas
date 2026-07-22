import apiClient from './apiClient';

export const leaveApi = {
  types: () => apiClient.get('/leave/types'),
  createType: (payload) => apiClient.post('/leave/types', payload),
  requests: (params = {}) => apiClient.get('/leave/requests', { params }),
  submit: (payload) => apiClient.post('/leave/requests', payload),
  approve: (id, payload = {}) => apiClient.patch(`/leave/requests/${id}/approve`, payload),
  reject: (id, payload = {}) => apiClient.patch(`/leave/requests/${id}/reject`, payload),
  balances: (params = {}) => apiClient.get('/leave/balances', { params }),
};
