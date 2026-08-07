import apiClient from './apiClient.js';

export const notificationApi = {
  list: (params = {}) => apiClient.get('/notifications', { params }),
  read: (id) => apiClient.patch(`/notifications/${id}/read`),
  readAll: () => apiClient.post('/notifications/read-all'),
};
