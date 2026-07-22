import apiClient from './apiClient';

export const onboardingApi = {
  templates: () => apiClient.get('/onboarding/templates'),
  createTemplate: (payload) => apiClient.post('/onboarding/templates', payload),
  assign: (payload) => apiClient.post('/onboarding/assign', payload),
  myTasks: () => apiClient.get('/onboarding/my-tasks'),
  complete: (id, payload = {}) => apiClient.patch(`/onboarding/tasks/${id}/complete`, payload),
};
