import {
  isProtectedAppPath,
  sessionExpiredPayload,
  shouldHandleSessionExpiry,
} from '../utils/sessionExpiry.js';

test('classifies protected-page 401 responses as expired sessions', () => {
  expect(
    shouldHandleSessionExpiry(
      { response: { status: 401 }, config: { url: '/employees' } },
      '/employees',
    ),
  ).toBe(true);

  expect(
    shouldHandleSessionExpiry(
      { response: { status: 401 }, config: { url: '/auth/me' } },
      '/dashboard',
    ),
  ).toBe(false);

  expect(
    shouldHandleSessionExpiry(
      { response: { status: 401 }, config: { url: '/auth/login' } },
      '/login',
    ),
  ).toBe(false);
});

test('keeps authentication-entry pages outside the protected session boundary', () => {
  expect(isProtectedAppPath('/forgot-password')).toBe(false);
  expect(isProtectedAppPath('/reset-password')).toBe(false);
  expect(isProtectedAppPath('/activate-account')).toBe(false);
  expect(isProtectedAppPath('/verify-email')).toBe(false);
});

test('replaces technical token details with the friendly session message', () => {
  const payload = sessionExpiredPayload({
    error: {
      code: 'JWT_EXPIRED',
      message: 'Token has expired',
    },
  });

  expect(payload.error.code).toBe('SESSION_EXPIRED');
  expect(payload.error.message).toBe(
    'Your session has expired. Please sign in again.',
  );
  expect(payload.error.message).not.toMatch(/token/i);
});
