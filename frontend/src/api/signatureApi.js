import apiClient from './apiClient';

export const signatureApi = {
  create: (payload) => apiClient.post('/signature-requests', payload),

  list: (params = {}) => apiClient.get(
    '/signature-requests',
    { params },
  ),

  get: (id) => apiClient.get(`/signature-requests/${id}`),

  myTasks: () => apiClient.get(
    '/signature-requests/my-tasks',
  ),

  viewed: (recipientId) => apiClient.patch(
    `/signature-requests/recipients/${recipientId}/viewed`,
  ),

  sign: (recipientId) => apiClient.patch(
    `/signature-requests/recipients/${recipientId}/sign`,
  ),

  decline: (recipientId, reason) => apiClient.patch(
    `/signature-requests/recipients/${recipientId}/decline`,
    { reason },
  ),
};
