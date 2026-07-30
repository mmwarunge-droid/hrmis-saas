import apiClient from './apiClient';

export const leaveApi = {
  setup: () => apiClient.get('/leave/setup'),

  saveGovernance: (payload) => apiClient.patch(
    '/leave/setup/governance',
    payload,
  ),

  applyStandardPack: (payload) => apiClient.post(
    '/leave/setup/standard-pack',
    payload,
  ),

  initializeBalances: (payload = {}) => apiClient.post(
    '/leave/setup/initialize-balances',
    payload,
  ),

  types: (params = {}) => apiClient.get(
    '/leave/types',
    { params },
  ),

  createType: (payload) => apiClient.post(
    '/leave/types',
    payload,
  ),

  requests: (params = {}) => apiClient.get(
    '/leave/requests',
    { params },
  ),

  submit: (payload) => apiClient.post(
    '/leave/requests',
    payload,
  ),

  approve: (id, payload = {}) => apiClient.patch(
    `/leave/requests/${id}/approve`,
    payload,
  ),

  reject: (id, payload = {}) => apiClient.patch(
    `/leave/requests/${id}/reject`,
    payload,
  ),

  balances: (params = {}) => apiClient.get(
    '/leave/balances',
    { params },
  ),
};
