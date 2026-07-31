import Dashboard from './Dashboard.jsx';
import EmployeeHome from './EmployeeHome.jsx';
import usePermissions from '../hooks/usePermissions.js';

const ADMIN_ROLES = [
  'SUPER_ADMIN',
  'ORGANIZATION_OWNER',
  'CLIENT_ADMIN',
  'HR_CONSULTANT',
];

const EMPLOYEE_HOME_ROLES = ['EMPLOYEE', 'MANAGER'];

export default function HomeRouter() {
  const { hasAnyRole } = usePermissions();

  // Employee self-service takes precedence for mixed-role accounts. This keeps
  // client administrators who are also employees on the welcoming homepage
  // and prevents administrative dashboard requests from running unnecessarily.
  if (hasAnyRole(EMPLOYEE_HOME_ROLES)) return <EmployeeHome />;
  return hasAnyRole(ADMIN_ROLES) ? <Dashboard /> : <EmployeeHome />;
}
