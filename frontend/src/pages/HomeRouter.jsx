import Dashboard from './Dashboard.jsx';
import EmployeeHome from './EmployeeHome.jsx';
import usePermissions from '../hooks/usePermissions.js';

const ADMIN_ROLES = [
  'SUPER_ADMIN',
  'ORGANIZATION_OWNER',
  'CLIENT_ADMIN',
  'HR_CONSULTANT',
];

export default function HomeRouter() {
  const { hasAnyRole } = usePermissions();
  return hasAnyRole(ADMIN_ROLES) ? <Dashboard /> : <EmployeeHome />;
}
