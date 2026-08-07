import apiClient from './apiClient';

export const onboardingApi = {
  templates: (params = {}) => apiClient.get('/onboarding/templates', { params }),
  createTemplate: (payload) => apiClient.post('/onboarding/templates', payload),
  updateTemplate: (id, payload) => apiClient.patch(`/onboarding/templates/${id}`, payload),
  assign: (payload) => apiClient.post('/onboarding/assign', payload),
  assignments: (params = {}) => apiClient.get('/onboarding/assignments', { params }),
  summary: () => apiClient.get('/onboarding/summary'),
  updateAssignment: (id, payload) => apiClient.patch(`/onboarding/assignments/${id}`, payload),
  myTasks: () => apiClient.get('/onboarding/my-tasks'),
  complete: (id, payload = {}) => apiClient.patch(`/onboarding/tasks/${id}/complete`, payload),
};
