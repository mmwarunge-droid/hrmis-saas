import apiClient from './apiClient';

export const departmentApi = {
  list: (params = {}) => apiClient.get('/employees/departments', { params }),
  create: (payload) => apiClient.post('/employees/departments', payload),
  update: (id, payload) => apiClient.patch(`/employees/departments/${id}`, payload),
  archive: (id, payload) => apiClient.post(`/employees/departments/${id}/archive`, payload),
  restore: (id) => apiClient.post(`/employees/departments/${id}/restore`),
  bulkTransfer: (payload) => apiClient.post('/employees/bulk-department-transfer', payload),
};
