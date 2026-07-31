import { Navigate, Outlet } from 'react-router-dom';

import usePermissions from '../hooks/usePermissions.js';

export default function PermissionRoute({
  permission = null,
  anyPermissions = [],
}) {
  const { hasPermission } = usePermissions();
  const allowed = permission
    ? hasPermission(permission)
    : anyPermissions.some((item) => hasPermission(item));

  if (!allowed) return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}
