import {
  BarChart3,
  Bot,
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
  UserRound,
  Users,
} from 'lucide-react';

export const navigationGroups = [
  {
    label: 'Workspace',
    links: [
      { to: '/dashboard', label: 'Home', icon: Home, permission: 'dashboard:read', keywords: 'dashboard overview' },
      { to: '/profile', label: 'My info', icon: UserRound, roles: ['EMPLOYEE', 'MANAGER'], keywords: 'profile personal information' },
      { to: '/tasks', label: 'My tasks', icon: CheckSquare2, keywords: 'checklist approvals work' },
      { to: '/ask-kinetic', label: 'Ask Kinetic', icon: Bot, keywords: 'help assistant guidance' },
    ],
  },
  {
    label: 'People',
    links: [
      { to: '/employees', label: 'People', icon: Users, permission: 'employee:read', keywords: 'employee directory staff' },
      { to: '/org-chart', label: 'Org chart', icon: Network, permission: 'employee:read', keywords: 'organization reporting structure' },
      { to: '/departments', label: 'Departments', icon: Briefcase, permission: 'employee:update', keywords: 'teams organization units' },
    ],
  },
  {
    label: 'Time',
    links: [
      { to: '/leave', label: 'Time off', icon: CalendarDays, permission: 'leave:create', keywords: 'leave vacation absence requests' },
      { to: '/attendance', label: 'Attendance', icon: BarChart3, permissionAny: ['attendance:read', 'attendance:write'], keywords: 'clock hours timesheet' },
    ],
  },
  {
    label: 'Workflows',
    links: [
      { to: '/documents', label: 'Files', icon: FileText, permission: 'document:read', keywords: 'documents contracts policies' },
      { to: '/signature-requests', label: 'Signatures', icon: FileSignature, permission: 'document:approve', keywords: 'electronic signing requests' },
      { to: '/onboarding', label: 'Onboarding', icon: UserPlus, permission: 'onboarding:create', keywords: 'new hires checklist' },
    ],
  },
  {
    label: 'Administration',
    links: [
      { to: '/organizations', label: 'Organizations', icon: Building2, role: 'SUPER_ADMIN', keywords: 'tenants clients companies' },
      { to: '/users', label: 'Access & users', icon: Users, permission: 'user:read', keywords: 'accounts roles permissions' },
      { to: '/settings/employee-experience', label: 'Employee experience', icon: Sparkles, roles: ['SUPER_ADMIN', 'ORGANIZATION_OWNER', 'CLIENT_ADMIN'], keywords: 'homepage branding events' },
      { to: '/settings', label: 'Settings', icon: Settings, keywords: 'security account preferences' },
    ],
  },
];

export function canViewNavigationItem(item, { hasPermission, hasRole }) {
  return (
    (!item.permission || hasPermission(item.permission))
    && (!item.permissionAny || item.permissionAny.some(hasPermission))
    && (!item.role || hasRole(item.role))
    && (!item.roles || item.roles.some(hasRole))
  );
}

export function visibleNavigation(groups, permissions) {
  return groups
    .map((group) => ({
      ...group,
      links: group.links.filter((item) => canViewNavigationItem(item, permissions)),
    }))
    .filter((group) => group.links.length > 0);
}

export const pageTitles = {
  '/dashboard': 'Home',
  '/employee-home': 'Home',
  '/profile': 'My info',
  '/ask-kinetic': 'Ask Kinetic',
  '/employees': 'People',
  '/org-chart': 'Org chart',
  '/departments': 'Departments',
  '/leave': 'Time off',
  '/attendance': 'Attendance',
  '/documents': 'Files',
  '/signature-requests': 'Signatures',
  '/tasks': 'Tasks',
  '/onboarding': 'Onboarding',
  '/users': 'Access & users',
  '/organizations': 'Organizations',
  '/settings': 'Settings',
  '/settings/employee-experience': 'Employee experience',
};

export function getPageTitle(pathname) {
  if (pathname.startsWith('/employees/')) return 'Employee profile';
  if (pathname.startsWith('/events/')) return 'Event';
  return pageTitles[pathname] || 'Kinetic';
}
