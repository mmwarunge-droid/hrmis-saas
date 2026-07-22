import { NavLink } from 'react-router-dom';
import { BarChart3, CalendarCheck, FileText, Home, Settings, UserPlus, Users } from 'lucide-react';
import usePermissions from '../../hooks/usePermissions';

const links = [
  { to: '/dashboard', label: 'Dashboard', icon: Home, permission: 'dashboard:read' },
  { to: '/employees', label: 'Employees', icon: Users, permission: 'employee:read' },
  { to: '/documents', label: 'Documents', icon: FileText, permission: 'document:read' },
  { to: '/leave', label: 'Leave', icon: CalendarCheck, permission: 'leave:create' },
  { to: '/attendance', label: 'Attendance', icon: BarChart3, permission: 'attendance:read' },
  { to: '/onboarding', label: 'Onboarding', icon: UserPlus, permission: 'onboarding:assign' },
  { to: '/users', label: 'Users', icon: Users, permission: 'user:read' },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const { hasPermission } = usePermissions();
  const visibleLinks = links.filter((link) => !link.permission || hasPermission(link.permission));
  return (
    <aside className="fixed inset-y-0 left-0 hidden w-72 border-r border-slate-200 bg-white p-5 lg:block">
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Consulting-Led</p>
        <h1 className="text-xl font-bold text-slate-950">HRMIS SaaS</h1>
      </div>
      <nav className="space-y-1">
        {visibleLinks.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium ${isActive ? 'bg-slate-950 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>
            <Icon size={18} /> {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
