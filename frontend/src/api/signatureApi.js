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

  recipient: (recipientId) => apiClient.get(
    `/signature-requests/recipients/${recipientId}`,
  ),

  viewed: (recipientId) => apiClient.patch(
    `/signature-requests/recipients/${recipientId}/viewed`,
  ),

  sign: (recipientId, signatureName) => apiClient.patch(
    `/signature-requests/recipients/${recipientId}/sign`,
    { signature_name: signatureName },
  ),

  discussion: (recipientId) => apiClient.get(
    `/signature-requests/recipients/${recipientId}/discussion`,
  ),

  comment: (recipientId, body) => apiClient.post(
    `/signature-requests/recipients/${recipientId}/discussion/comments`,
    { body },
  ),

  resolveDiscussion: (recipientId) => apiClient.patch(
    `/signature-requests/recipients/${recipientId}/discussion/resolve`,
  ),

  decline: (recipientId, reason) => apiClient.patch(
    `/signature-requests/recipients/${recipientId}/decline`,
    { reason },
  ),

  remind: (requestId) => apiClient.post(
    `/signature-requests/${requestId}/remind`,
  ),

  updateDeadline: (requestId, dueAt) => apiClient.patch(
    `/signature-requests/${requestId}/deadline`,
    { due_at: dueAt },
  ),

  cancel: (requestId, reason) => apiClient.patch(
    `/signature-requests/${requestId}/cancel`,
    { reason },
  ),

  evidence: (requestId) => apiClient.get(
    `/signature-requests/${requestId}/evidence`,
  ),

  retryEvidence: (requestId) => apiClient.post(
    `/signature-requests/${requestId}/evidence/retry`,
  ),

  artifactDownloadUrl: (requestId, artifactId) => {
    const base = apiClient.defaults.baseURL || '/api';

    return `${base}/signature-requests/${requestId}`
      + `/artifacts/${artifactId}/download`;
  },
};
