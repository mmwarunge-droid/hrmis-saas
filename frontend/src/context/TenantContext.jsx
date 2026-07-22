import { createContext, useMemo, useState } from 'react';

export const TenantContext = createContext(null);

export function TenantProvider({ children }) {
  const [tenantId, setTenantId] = useState(null);
  const value = useMemo(() => ({ tenantId, setTenantId }), [tenantId]);
  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
}
