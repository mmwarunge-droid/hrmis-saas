export const SESSION_EXPIRED_EVENT = 'kinetic:session-expired';
export const SESSION_EXPIRED_MESSAGE = 'Your session has expired. Please sign in again.';

const PUBLIC_AUTH_PATHS = [
  '/login',
  '/mfa',
  '/forgot-password',
  '/reset-password',
  '/activate-account',
  '/verify-email',
];

const SESSION_BOOTSTRAP_ENDPOINTS = [
  '/auth/login',
  '/auth/me',
  '/auth/refresh',
];

export function isProtectedAppPath(pathname = '/') {
  return !PUBLIC_AUTH_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`),
  );
}

export function shouldHandleSessionExpiry(
  error,
  pathname = typeof window === 'undefined' ? '/' : window.location.pathname,
) {
  if (error.response?.status !== 401 || !isProtectedAppPath(pathname)) {
    return false;
  }

  const requestUrl = error.config?.url || '';
  return !SESSION_BOOTSTRAP_ENDPOINTS.some((endpoint) => (
    requestUrl === endpoint || requestUrl.startsWith(`${endpoint}?`)
  ));
}

export function signalSessionExpired() {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
}

export function sessionExpiredPayload(payload = {}) {
  return {
    ...payload,
    success: false,
    error: {
      ...(payload.error || {}),
      code: 'SESSION_EXPIRED',
      message: SESSION_EXPIRED_MESSAGE,
    },
  };
}
