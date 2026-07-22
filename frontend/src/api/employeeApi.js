import apiClient from './apiClient';

export const employeeApi = {
  list: (params = {}) => apiClient.get('/employees', { params }),
  get: (id) => apiClient.get(`/employees/${id}`),
  create: (payload) => apiClient.post('/employees', payload),
  update: (id, payload) => apiClient.patch(`/employees/${id}`, payload),
  remove: (id) => apiClient.delete(`/employees/${id}`),
  departments: () => apiClient.get('/employees/departments'),
};
