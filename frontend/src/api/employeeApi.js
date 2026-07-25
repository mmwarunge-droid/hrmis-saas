import apiClient from './apiClient';

export const employeeApi = {
  list: (params = {}) => apiClient.get('/employees', { params }),
  get: (id) => apiClient.get(`/employees/${id}`),
  history: (id) => apiClient.get(`/employees/${id}/job-history`),
  create: (payload) => apiClient.post('/employees', payload),
  update: (id, payload) => apiClient.patch(`/employees/${id}`, payload),
  remove: (id) => apiClient.delete(`/employees/${id}`),
  departments: (params = {}) => apiClient.get('/employees/departments', { params }),
  options: () => apiClient.get('/employees/options'),
  orgChart: () => apiClient.get('/employees/org-chart'),
};
