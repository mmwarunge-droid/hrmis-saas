import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { tenantApi } from '../api/tenantApi.js';
import useAuth from '../hooks/useAuth.js';
import {
  readActiveTenantId,
  writeActiveTenantId,
} from '../utils/tenantScope.js';

export const TenantContext = createContext(null);

export function TenantProvider({ children }) {
  const { user, loading: authLoading } = useAuth();
  const [tenantId, setTenantIdState] = useState(
    () => readActiveTenantId(),
  );
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const isSuperAdmin = Boolean(
    user?.roles?.includes('SUPER_ADMIN'),
  );

  const setTenantId = useCallback((nextTenantId) => {
    const next = nextTenantId ? String(nextTenantId) : null;
    setTenantIdState(next);
    writeActiveTenantId(next);
  }, []);

  const clearTenant = useCallback(() => {
    setTenantIdState(null);
    writeActiveTenantId(null);
  }, []);

  const reloadTenants = useCallback(async () => {
    if (!isSuperAdmin) {
      setTenants([]);
      return [];
    }

    setLoading(true);
    setError('');

    try {
      const response = await tenantApi.options();
      const items = (response.data.items || []).filter(
        (tenant) => tenant.status === 'active',
      );
      const storedTenantId = readActiveTenantId();

      setTenants(items);

      if (
        storedTenantId
        && items.some(
          (tenant) => String(tenant.id) === storedTenantId,
        )
      ) {
        setTenantIdState(storedTenantId);
      } else {
        clearTenant();
      }

      return items;
    } catch (err) {
      setTenants([]);
      setError(
        err.error?.message
        || 'Unable to load organizations',
      );
      return [];
    } finally {
      setLoading(false);
    }
  }, [clearTenant, isSuperAdmin]);

  useEffect(() => {
    if (authLoading) return;

    if (!user) {
      setTenants([]);
      clearTenant();
      return;
    }

    if (!isSuperAdmin) {
      setTenants([]);
      setError('');
      writeActiveTenantId(null);
      setTenantIdState(
        user.tenant_id ? String(user.tenant_id) : null,
      );
      return;
    }

    reloadTenants();
  }, [
    authLoading,
    clearTenant,
    isSuperAdmin,
    reloadTenants,
    user,
  ]);

  const activeTenant = useMemo(
    () => tenants.find(
      (tenant) => String(tenant.id) === tenantId,
    ) || null,
    [tenantId, tenants],
  );

  const value = useMemo(
    () => ({
      tenantId,
      activeTenant,
      tenants,
      loading,
      error,
      isSuperAdmin,
      requiresTenantSelection: isSuperAdmin && !tenantId,
      setTenantId,
      clearTenant,
      reloadTenants,
    }),
    [
      activeTenant,
      clearTenant,
      error,
      isSuperAdmin,
      loading,
      reloadTenants,
      setTenantId,
      tenantId,
      tenants,
    ],
  );

  return (
    <TenantContext.Provider value={value}>
      {children}
    </TenantContext.Provider>
  );
}
