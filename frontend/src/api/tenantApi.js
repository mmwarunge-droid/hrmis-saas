import apiClient from './apiClient';

export const tenantApi = {
  list: (params = {}) => apiClient.get('/tenants', { params }),
  summary: () => apiClient.get('/tenants/summary'),
  options: () => apiClient.get('/tenants/options'),
  get: (id) => apiClient.get(`/tenants/${id}`),
  create: (payload) => apiClient.post('/tenants', payload),
  provision: (payload) => apiClient.post('/tenants/provision', payload),
  update: (id, payload) => apiClient.patch(`/tenants/${id}`, payload),
  mfaPolicy: (id) => apiClient.get(`/tenants/${id}/mfa-policy`),
  updateMfaPolicy: (id, payload) => apiClient.patch(`/tenants/${id}/mfa-policy`, payload),
  mfaCompliance: (id) => apiClient.get(`/tenants/${id}/mfa-compliance`),
};
