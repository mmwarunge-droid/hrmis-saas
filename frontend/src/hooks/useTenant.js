import { useContext } from 'react';

import { TenantContext } from '../context/TenantContext.jsx';

export default function useTenant() {
  const context = useContext(TenantContext);

  if (!context) {
    throw new Error(
      'useTenant must be used within TenantProvider',
    );
  }

  return context;
}
