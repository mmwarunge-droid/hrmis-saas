const owners = new Map();
let current = null;
let turn = 0;

export function registerWorkflow(id, owner) {
  owners.set(id, owner);
  return () => owners.delete(id);
}
export function captureWorkflow(id) {
  const sequence = ++turn;
  current = id;
  queueMicrotask(() => { if (sequence === turn) current = null; });
}
export function requestWorkflow(_method) {
  if (current && owners.has(current)) return current;
  const submitting = [...owners.entries()].filter(([, owner]) => owner.submitting?.());
  if (submitting.length === 1) return submitting[0][0];
  // After await, the original event turn has ended. Keep feedback in the
  // foreground workflow, including GET-based preflight validation.
  if (typeof document !== 'undefined') {
    const dialogs = document.querySelectorAll('[data-modal-overlay]');
    const dialog = dialogs[dialogs.length - 1];
    const active = document.activeElement;
    const element = dialog && !dialog.contains(active) ? dialog : active?.closest?.('[data-workflow-owner]');
    const ownerId = element?.getAttribute('data-workflow-owner');
    if (ownerId && owners.has(ownerId)) return ownerId;
  }
  return null;
}
export function workflowRequest(id, method) { owners.get(id)?.start?.(method); }
export function workflowResponse(id, error, response) { owners.get(id)?.settle?.(error, response); }
export function hasUnsavedWork() { return [...owners.values()].some((owner) => owner.dirty?.()); }
export function notifySessionExpiry(error) {
  for (const owner of owners.values()) if (owner.dirty?.()) owner.error?.(error);
}

export function flattenErrors(value, path = '') {
  if (typeof value === 'string') return [{ field: path, message: value }];
  if (Array.isArray(value)) return value.flatMap((item, index) => flattenErrors(item, typeof item === 'string' ? path : [path, index].filter((v) => v !== '').join('.')));
  if (value && typeof value === 'object') return Object.entries(value).flatMap(([key, item]) => flattenErrors(item, [path, key].filter(Boolean).join('.')));
  return [];
}
export function fieldLabel(path = '') {
  return path.replace(/^recipients\.(\d+)\.?/, (_, index) => `Signatory ${Number(index) + 1}: `)
    .replace(/employee_id/g, 'employee').replace(/due_at/g, 'completion deadline').replace(/_/g, ' ').replace(/\./g, ' — ');
}
export function normalizeApiError(error) {
  const status = error.response?.status ?? error.httpStatus ?? error.error?.status;
  const payload = error.response?.data || (error.error ? error : {});
  const authenticationAttempt = error.authenticationAttempt || /\/auth\/(login|mfa|forgot-password|reset-password|activate|verify)/.test(error.config?.url || '');
  const original = payload.error?.message || (error instanceof Error && !error.isAxiosError ? error.message : undefined);
  const fields = payload.error?.fields || (original && typeof original === 'object' ? original : {});
  const issues = flattenErrors(fields);
  let message = typeof original === 'string' ? original : '';
  const code = payload.error?.code || error.code || 'NETWORK_ERROR';
  if (status === 401 && !authenticationAttempt) message = 'Your session expired. Sign in again to continue; your entries are still here.';
  else if (status === 403) message = 'You do not have permission to perform this action. Contact your administrator; your entries are still here.';
  else if (status >= 500) message = 'The server could not complete this action. Your entries are intact. Please try again shortly.';
  else if (['ECONNABORTED', 'ETIMEDOUT', 'REQUEST_TIMEOUT'].includes(code)) message = 'The request timed out. Your entries are intact. Check whether the action completed before retrying.';
  else if (!status && !message && !issues.length) message = 'Unable to connect. Check your connection and try again; your entries are still here.';
  return { ...payload, authenticationAttempt, success: false, httpStatus: status, error: { ...payload.error, code,
    status, message: message || 'Please correct the following fields and try again.', fields, issues } };
}
export function errorState(error) {
  const normalized = normalizeApiError(typeof error === 'string' ? { error: { message: error } } : error || {});
  return { kind: 'error', message: normalized.error.message, issues: normalized.error.issues, status: normalized.httpStatus, authenticationAttempt: normalized.authenticationAttempt };
}

export function requestWorkflowExit(action, cancel) {
  const changed = [...owners.values()].filter((owner) => owner.dirty?.());
  const next = (index) => index < changed.length ? changed[index].leave?.(() => next(index + 1), cancel) : action();
  next(0);
}
