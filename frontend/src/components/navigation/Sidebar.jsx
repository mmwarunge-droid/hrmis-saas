import {
  BarChart3,
  Briefcase,
  Building2,
  CalendarDays,
  CheckSquare2,
  FileSignature,
  FileText,
  Home,
  Network,
  Settings,
  Sparkles,
  UserPlus,
  Users,
  X,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import useAuth from '../../hooks/useAuth.js';
import usePermissions from '../../hooks/usePermissions.js';
import Avatar from '../ui/Avatar.jsx';
import Button from '../ui/Button.jsx';

const groups = [
  {
    label: 'Workspace',
    links: [
      { to: '/dashboard', label: 'Home', icon: Home, permission: 'dashboard:read' },
      { to: '/tasks', label: 'My tasks', icon: CheckSquare2, permission: 'onboarding:assign' },
    ],
  },
  {
    label: 'People',
    links: [
      { to: '/employees', label: 'People directory', icon: Users, permission: 'employee:read' },
      { to: '/org-chart', label: 'Org chart', icon: Network, permission: 'employee:read' },
      { to: '/leave', label: 'Time off', icon: CalendarDays, permission: 'leave:create' },
      { to: '/attendance', label: 'Attendance', icon: BarChart3, permissionAny: ['attendance:read', 'attendance:write'] },
    ],
  },
  {
    label: 'Operations',
    links: [
      { to: '/documents', label: 'Docs', icon: FileText, permission: 'document:read' },
      {
        to: '/signature-requests',
        label: 'Signature requests',
        icon: FileSignature,
        permission: 'document:approve',
      },
      { to: '/onboarding', label: 'Onboarding', icon: UserPlus, permission: 'onboarding:create' },
    ],
  },
  {
    label: 'Administration',
    links: [
      { to: '/organizations', label: 'Organizations', icon: Building2, role: 'SUPER_ADMIN' },
      { to: '/departments', label: 'Departments', icon: Briefcase, permission: 'employee:update' },
      { to: '/users', label: 'Access & users', icon: Users, permission: 'user:read' },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
];

export default function Sidebar({ open = false, onClose }) {
  const { user } = useAuth();
  const { hasPermission, hasRole } = usePermissions();

  const content = (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-cyan-400 to-blue-600 text-white shadow-lg shadow-cyan-950/20"><Sparkles size={20} /></span>
          <div><p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">People OS</p><h1 className="text-lg font-bold text-white">ACE</h1></div>
        </div>
        <Button variant="ghost" size="sm" className="text-slate-300 hover:bg-white/10 hover:text-white lg:hidden" onClick={onClose}><X size={18} /></Button>
      </div>

      <nav className="mt-8 flex-1 space-y-6 overflow-y-auto pr-1">
        {groups.map((group) => {
          const visible = group.links.filter((link) => (!link.permission || hasPermission(link.permission)) && (!link.permissionAny || link.permissionAny.some(hasPermission)) && (!link.role || hasRole(link.role)));
          if (!visible.length) return null;
          return (
            <div key={group.label}>
              <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.22em] text-slate-500">{group.label}</p>
              <div className="space-y-1">
                {visible.map(({ to, label, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    onClick={onClose}
                    className={({ isActive }) => `group flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-medium transition ${isActive ? 'bg-white text-slate-950 shadow-lg' : 'text-slate-300 hover:bg-white/10 hover:text-white'}`}
                  >
                    <Icon size={18} /> <span>{label}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          );
        })}
      </nav>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-3">
        <div className="flex items-center gap-3">
          <Avatar name={user?.full_name} size="sm" />
          <div className="min-w-0"><p className="truncate text-sm font-semibold text-white">{user?.full_name}</p><p className="truncate text-[11px] text-slate-400">{user?.roles?.[0]?.replaceAll('_', ' ')}</p></div>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-72 bg-slate-950 p-5 lg:block">{content}</aside>
      {open && <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm lg:hidden" onClick={onClose}><aside className="h-full w-72 bg-slate-950 p-5" onClick={(event) => event.stopPropagation()}>{content}</aside></div>}
    </>
  );
}
