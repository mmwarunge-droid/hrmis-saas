import apiClient from './apiClient';

export const employeeApi = {
  list: (params = {}) => apiClient.get('/employees', { params }),
  accessDirectory: (params = {}) => apiClient.get('/employees/access-directory', { params }),
  summary: () => apiClient.get('/employees/summary'),
  get: (id) => apiClient.get(`/employees/${id}`),
  history: (id) => apiClient.get(`/employees/${id}/job-history`),
  provisionAccess: (id, payload) => apiClient.post(`/employees/${id}/provision-access`, payload),
  updateAccess: (id, payload) => apiClient.patch(`/employees/${id}/access`, payload),
  create: (payload) => apiClient.post('/employees', payload),
  update: (id, payload) => apiClient.patch(`/employees/${id}`, payload),
  remove: (id) => apiClient.delete(`/employees/${id}`),
  departments: (params = {}) => apiClient.get('/employees/departments', { params }),
  options: () => apiClient.get('/employees/options'),
  orgChart: () => apiClient.get('/employees/org-chart'),
};
