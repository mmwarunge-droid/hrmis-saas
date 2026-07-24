import apiClient from './apiClient';

export const tenantApi = {
  list: (params = {}) => apiClient.get('/tenants', { params }),
  get: (id) => apiClient.get(`/tenants/${id}`),
  create: (payload) => apiClient.post('/tenants', payload),
  provision: (payload) => apiClient.post('/tenants/provision', payload),
  update: (id, payload) => apiClient.patch(`/tenants/${id}`, payload),
};
