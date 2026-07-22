import apiClient from './apiClient';

export const userApi = {
  list: () => apiClient.get('/users'),
  create: (payload) => apiClient.post('/users', payload),
  update: (id, payload) => apiClient.patch(`/users/${id}`, payload),
  updateRoles: (id, roles) => apiClient.patch(`/users/${id}/roles`, { roles }),
};
