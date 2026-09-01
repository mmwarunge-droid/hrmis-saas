import apiClient from './apiClient';

export const onboardingApi = {
  templates: (params = {}) => apiClient.get('/onboarding/templates', { params }),
  createTemplate: (payload) => apiClient.post('/onboarding/templates', payload),
  updateTemplate: (id, payload) => apiClient.patch(`/onboarding/templates/${id}`, payload),
  uploadResource: (formData) => apiClient.post(
    '/onboarding/resources',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  ),
  resourceContentUrl: (resourceId, tenantId = '') => {
    const base = apiClient.defaults.baseURL || '/api';
    const tenantQuery = tenantId
      ? `?tenant_id=${encodeURIComponent(tenantId)}`
      : '';
    return `${base}/onboarding/resources/${resourceId}/content${tenantQuery}`;
  },
  assign: (payload) => apiClient.post('/onboarding/assign', payload),
  assignments: (params = {}) => apiClient.get('/onboarding/assignments', { params }),
  summary: () => apiClient.get('/onboarding/summary'),
  updateAssignment: (id, payload) => apiClient.patch(`/onboarding/assignments/${id}`, payload),
  attempts: (id) => apiClient.get(`/onboarding/assignments/${id}/attempts`),
  retake: (id, payload) => apiClient.post(
    `/onboarding/assignments/${id}/retake`,
    payload,
  ),
  myTasks: () => apiClient.get('/onboarding/my-tasks'),
  viewed: (id) => apiClient.patch(`/onboarding/tasks/${id}/view`),
  videoProgress: (id, payload) => apiClient.patch(
    `/onboarding/tasks/${id}/video-progress`,
    payload,
  ),
  complete: (id, payload = {}) => apiClient.patch(`/onboarding/tasks/${id}/complete`, payload),
};
