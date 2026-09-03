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

  signingDocument: (recipientId) => apiClient.get(
    `/signature-requests/recipients/${recipientId}/document`,
    { responseType: 'blob' },
  ),

  signedDocument: (recipientId) => apiClient.get(
    `/signature-requests/recipients/${recipientId}/signed-document`,
    { responseType: 'blob' },
  ),

  signedDocumentUrl: (recipientId) => {
    const base = apiClient.defaults.baseURL || '/api';
    return `${base}/signature-requests/recipients/${recipientId}/signed-document`;
  },

  submit: (recipientId, payload) => apiClient.post(
    `/signature-requests/recipients/${recipientId}/submit`,
    payload,
  ),

  sign: (recipientId, signatureName) => apiClient.patch(
    `/signature-requests/recipients/${recipientId}/sign`,
    { signature_name: signatureName },
  ),

  discussion: (recipientId) => apiClient.get(
    `/signature-requests/recipients/${recipientId}/discussion`,
  ),

  comment: (recipientId, body, mentionedUserIds = []) => apiClient.post(
    `/signature-requests/recipients/${recipientId}/discussion/comments`,
    {
      body,
      mentioned_user_ids: mentionedUserIds,
    },
  ),

  discussionMentions: (recipientId, q) => apiClient.get(
    `/signature-requests/recipients/${recipientId}/discussion/mentions`,
    { params: { q } },
  ),

  updateComment: (
    recipientId,
    commentId,
    body,
    mentionedUserIds = [],
  ) => apiClient.patch(
    `/signature-requests/recipients/${recipientId}/discussion/comments/${commentId}`,
    {
      body,
      mentioned_user_ids: mentionedUserIds,
    },
  ),

  deleteComment: (recipientId, commentId) => apiClient.delete(
    `/signature-requests/recipients/${recipientId}/discussion/comments/${commentId}`,
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

  resend: (requestId, payload) => apiClient.post(
    `/signature-requests/${requestId}/resend`,
    payload,
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

  artifact: (requestId, artifactId) => apiClient.get(
    `/signature-requests/${requestId}/artifacts/${artifactId}/download`,
    { responseType: 'blob' },
  ),

  sealImage: (requestId) => apiClient.get(
    `/signature-requests/${requestId}/seal/image`,
    { responseType: 'blob' },
  ),

  uploadSealImage: (requestId, file) => {
    const formData = new FormData();
    formData.append('file', file);

    return apiClient.post(
      `/signature-requests/${requestId}/seal/image`,
      formData,
    );
  },

  updateSealPlacement: (requestId, placement) => apiClient.patch(
    `/signature-requests/${requestId}/seal/placement`,
    placement,
  ),

  artifactDownloadUrl: (requestId, artifactId) => {
    const base = apiClient.defaults.baseURL || '/api';

    return `${base}/signature-requests/${requestId}`
      + `/artifacts/${artifactId}/download`;
  },
};
