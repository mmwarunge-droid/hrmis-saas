const ACTIVE_TENANT_STORAGE_KEY = 'kinetic.activeTenantId';
const LEGACY_ACTIVE_TENANT_STORAGE_KEY = 'ace.activeTenantId';

const TENANT_SCOPED_PREFIXES = [
  '/dashboard',
  '/employees',
  '/documents',
  '/signature-requests',
  '/leave',
  '/attendance',
  '/onboarding',
];

function normalizePath(url = '') {
  try {
    const path = new URL(url, 'https://kinetic.invalid').pathname;
    return path.replace(/^\/api(?=\/)/, '');
  } catch {
    return String(url).split('?')[0].replace(/^\/api(?=\/)/, '');
  }
}

export function isTenantScopedRequest(url) {
  const path = normalizePath(url);
  return TENANT_SCOPED_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}

export function readActiveTenantId() {
  if (typeof window === 'undefined') return null;

  try {
    const current = window.sessionStorage.getItem(ACTIVE_TENANT_STORAGE_KEY);
    if (current) return current;

    const legacy = window.sessionStorage.getItem(LEGACY_ACTIVE_TENANT_STORAGE_KEY);
    if (legacy) {
      window.sessionStorage.setItem(ACTIVE_TENANT_STORAGE_KEY, legacy);
      window.sessionStorage.removeItem(LEGACY_ACTIVE_TENANT_STORAGE_KEY);
      return legacy;
    }

    return null;
  } catch {
    return null;
  }
}

export function writeActiveTenantId(tenantId) {
  if (typeof window === 'undefined') return;

  try {
    if (tenantId) {
      window.sessionStorage.setItem(ACTIVE_TENANT_STORAGE_KEY, String(tenantId));
    } else {
      window.sessionStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY);
    }
    window.sessionStorage.removeItem(LEGACY_ACTIVE_TENANT_STORAGE_KEY);
  } catch {
    // Storage can be unavailable in restricted browser contexts.
  }
}

export function withActiveTenantParams(url, params = {}) {
  const tenantId = readActiveTenantId();

  if (!tenantId || !isTenantScopedRequest(url)) return params;

  if (params instanceof URLSearchParams) {
    const next = new URLSearchParams(params);
    if (!next.has('tenant_id')) next.set('tenant_id', tenantId);
    return next;
  }

  return { ...params, tenant_id: params?.tenant_id || tenantId };
}

export { ACTIVE_TENANT_STORAGE_KEY };
