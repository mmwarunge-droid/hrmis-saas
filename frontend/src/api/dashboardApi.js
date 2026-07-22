import apiClient from './apiClient';

export const dashboardApi = {
  summary: () => apiClient.get('/dashboard/summary'),
  complianceAlerts: () => apiClient.get('/dashboard/compliance-alerts'),
  leaveSummary: () => apiClient.get('/dashboard/leave-summary'),
};
