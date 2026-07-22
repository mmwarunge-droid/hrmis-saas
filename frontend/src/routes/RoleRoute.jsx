import { Navigate, Outlet } from 'react-router-dom';
import usePermissions from '../hooks/usePermissions';

export default function RoleRoute({ roles = [] }) {
  const { hasAnyRole } = usePermissions();
  if (!hasAnyRole(roles)) return <Navigate to="/unauthorized" replace />;
  return <Outlet />;
}
