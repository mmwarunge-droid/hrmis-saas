import {
  ACTIVE_TENANT_STORAGE_KEY,
  isTenantScopedRequest,
  withActiveTenantParams,
} from '../utils/tenantScope.js';

beforeEach(() => {
  sessionStorage.clear();
});

test('adds the active tenant to tenant-scoped API requests', () => {
  sessionStorage.setItem(
    ACTIVE_TENANT_STORAGE_KEY,
    'tenant-1',
  );

  expect(
    withActiveTenantParams('/employees/departments', {
      include_archived: true,
    }),
  ).toEqual({
    include_archived: true,
    tenant_id: 'tenant-1',
  });

  expect(
    withActiveTenantParams('/signature-requests', {
      status: 'sent',
    }),
  ).toEqual({
    status: 'sent',
    tenant_id: 'tenant-1',
  });
});

test('does not override an explicit tenant or scope platform APIs', () => {
  sessionStorage.setItem(
    ACTIVE_TENANT_STORAGE_KEY,
    'tenant-1',
  );

  expect(
    withActiveTenantParams('/employees', {
      tenant_id: 'tenant-2',
    }),
  ).toEqual({
    tenant_id: 'tenant-2',
  });

  expect(
    withActiveTenantParams('/tenants', {
      page: 1,
    }),
  ).toEqual({
    page: 1,
  });

  expect(isTenantScopedRequest('/api/employees')).toBe(true);
  expect(isTenantScopedRequest('/api/tenants')).toBe(false);
});
