import useAuth from './useAuth';

export default function usePermissions() {
  const { user } = useAuth();
  const permissions = new Set(user?.permissions || []);
  const roles = new Set(user?.roles || []);
  return {
    hasPermission: (permission) => roles.has('SUPER_ADMIN') || permissions.has(permission),
    hasRole: (role) => roles.has(role),
    hasAnyRole: (allowed) => allowed.some((role) => roles.has(role)),
  };
}
