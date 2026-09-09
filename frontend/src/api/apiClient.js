import { requestWorkflow, workflowRequest, workflowResponse, normalizeApiError, hasUnsavedWork, notifySessionExpiry } from '../utils/formFeedback.js';
import axios from 'axios';

import { withActiveTenantParams } from '../utils/tenantScope.js';
import {
  sessionExpiredPayload,
  shouldHandleSessionExpiry,
  signalSessionExpired,
} from '../utils/sessionExpiry.js';

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

if (import.meta.env.PROD && !configuredBaseUrl) {
  throw new Error('VITE_API_BASE_URL must be configured for production builds');
}

const MUTATING_METHODS = new Set(['post', 'put', 'patch', 'delete']);

function readCookie(name) {
  const prefix = `${encodeURIComponent(name)}=`;
  const cookie = document.cookie
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));

  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

const apiClient = axios.create({
  baseURL: configuredBaseUrl || '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  if (!config.skipWorkflowFeedback) {
    config.workflowOwner = requestWorkflow(config.method?.toLowerCase());
    workflowRequest(config.workflowOwner, config.method);
  }
  config.params = withActiveTenantParams(
    config.url,
    config.params,
  );

  const method = config.method?.toLowerCase();
  if (!MUTATING_METHODS.has(method)) return config;

  const isRefreshRequest = config.url?.includes('/auth/refresh');
  const csrfCookieName = isRefreshRequest
    ? 'csrf_refresh_token'
    : 'csrf_access_token';
  const csrfToken = readCookie(csrfCookieName);

  if (csrfToken) {
    config.headers.set('X-CSRF-TOKEN', csrfToken);
  }

  return config;
}, undefined, { synchronous: true });

apiClient.interceptors.response.use(
  (response) => {
    workflowResponse(response.config?.workflowOwner, null, response.data);
    return response.data;
  },
  (error) => {
    let payload = normalizeApiError(error);
    if (shouldHandleSessionExpiry(error)) {
      if (hasUnsavedWork() || error.config?.workflowOwner) {
        notifySessionExpiry(payload);
      } else {
        signalSessionExpired();
        payload = sessionExpiredPayload(payload);
      }
    }
    workflowResponse(error.config?.workflowOwner, payload);
    return Promise.reject(payload);
  },
);

export default apiClient;
