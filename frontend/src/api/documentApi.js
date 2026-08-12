import apiClient from './apiClient';

export const documentApi = {
  list: (params = {}) => apiClient.get('/documents', { params }),
  summary: () => apiClient.get('/documents/summary'),
  upload: (formData) => apiClient.post('/documents/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  get: (id) => apiClient.get(`/documents/${id}`),
  update: (id, payload) => apiClient.patch(`/documents/${id}`, payload),
  downloadUrl: (id) => `${apiClient.defaults.baseURL}/documents/${id}/download`,
  content: (id) => apiClient.get(`/documents/${id}/content`, { responseType: 'blob' }),
};
