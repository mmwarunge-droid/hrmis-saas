import apiClient from './apiClient';

export const userApi = {
  list: (params = {}) => apiClient.get('/users', { params }),
  summary: (params = {}) => apiClient.get('/users/summary', { params }),
  options: (params = {}) => apiClient.get('/users/options', { params }),
  create: (payload) => apiClient.post('/users', payload),
  update: (id, payload) => apiClient.patch(`/users/${id}`, payload),
  updateRoles: (id, roles) => apiClient.patch(`/users/${id}/roles`, { roles }),
  linkEmployee: (id, employeeId) => apiClient.patch(`/users/${id}/employee-link`, { employee_id: employeeId }),
  resetMfa: (id, payload) => apiClient.post(`/users/${id}/mfa/reset`, payload),
  resendInvitation: (id) => apiClient.post(`/users/${id}/invitation/resend`),
  shareAccessLink: (id) => apiClient.post(`/users/${id}/access-link/share`),
  sharePasswordResetBulk: (payload) => apiClient.post('/users/password-reset/share-bulk', payload),
};
