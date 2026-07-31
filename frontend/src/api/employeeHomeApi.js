import apiClient from './apiClient';

export const employeeHomeApi = {
  get: () => apiClient.get('/employee-home'),
  updateProfile: (payload) => apiClient.patch('/employee-home/profile', payload),
  uploadProfileImage: (asset, file) => {
    const form = new FormData();
    form.append('file', file);
    return apiClient.post(
      `/employee-home/profile-image/${asset}`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  },
  event: (id) => apiClient.get(`/employee-home/events/${id}`),
  settings: (tenantId) => apiClient.get(`/tenants/${tenantId}/homepage-settings`),
  updateSettings: (tenantId, payload) => apiClient.patch(
    `/tenants/${tenantId}/homepage-settings`,
    payload,
  ),
  uploadBranding: (tenantId, asset, file) => {
    const form = new FormData();
    form.append('file', file);
    return apiClient.post(
      `/tenants/${tenantId}/homepage-branding/${asset}`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  },
  events: (tenantId) => apiClient.get(`/tenants/${tenantId}/events`),
  createEvent: (tenantId, payload) => apiClient.post(
    `/tenants/${tenantId}/events`,
    payload,
  ),
  updateEvent: (tenantId, id, payload) => apiClient.patch(
    `/tenants/${tenantId}/events/${id}`,
    payload,
  ),
  removeEvent: (tenantId, id) => apiClient.delete(
    `/tenants/${tenantId}/events/${id}`,
  ),
  documentOptions: (tenantId) => apiClient.get(
    `/tenants/${tenantId}/homepage-document-options`,
  ),
  essentials: (tenantId) => apiClient.get(`/tenants/${tenantId}/essentials`),
  createEssential: (tenantId, payload) => apiClient.post(
    `/tenants/${tenantId}/essentials`,
    payload,
  ),
  updateEssential: (tenantId, id, payload) => apiClient.patch(
    `/tenants/${tenantId}/essentials/${id}`,
    payload,
  ),
  removeEssential: (tenantId, id) => apiClient.delete(
    `/tenants/${tenantId}/essentials/${id}`,
  ),
};
