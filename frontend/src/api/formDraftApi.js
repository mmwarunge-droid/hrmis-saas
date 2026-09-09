import apiClient from './apiClient.js';
const options = (ownerId, extra = {}) => ({ skipWorkflowFeedback: true, params: { ...(ownerId ? { owner_id: ownerId } : {}), ...extra } });
export const formDraftApi = {
  list: (ownerId) => apiClient.get('/form-drafts', options(ownerId)),
  get: (key, ownerId) => apiClient.get(`/form-drafts/${encodeURIComponent(key)}`, options(ownerId)),
  save: (key, payload, ownerId) => apiClient.put(`/form-drafts/${encodeURIComponent(key)}`, payload, options(ownerId)),
  discard: (key, revision, ownerId) => apiClient.delete(`/form-drafts/${encodeURIComponent(key)}`, options(ownerId, { revision })),
};
