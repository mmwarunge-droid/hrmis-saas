import {
  BarChart3,
  Bot,
  Briefcase,
  Building2,
  CalendarDays,
  CheckSquare2,
  FileSignature,
  FileText,
  LifeBuoy,
  Home,
  Network,
  Settings,
  Sparkles,
  Target,
  UserPlus,
  UserRound,
  Users,
} from 'lucide-react';

export const navigationGroups = [
  {
    label: 'Workspace',
    links: [
      { to: '/dashboard', label: 'Home', icon: Home, permission: 'dashboard:read', keywords: 'dashboard overview' },
      { to: '/profile', label: 'My info', icon: UserRound, requiresEmployeeProfile: true, keywords: 'profile personal information' },
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
      { to: '/leave/setup', label: 'Time-off setup', icon: Settings, permission: 'leave:approve', keywords: 'leave policy governance balances accruals' },
    ],
  },
  {
    label: 'Performance',
    links: [
      { to: '/goals', label: 'Goals & KPIs', icon: Target, permission: 'goal:read', keywords: 'performance objectives targets kpi check ins' },
    ],
  },
  {
    label: 'Workflows',
    links: [
      { to: '/documents', label: 'Files', icon: FileText, permission: 'document:read', keywords: 'documents contracts policies' },
      { to: '/signature-requests', label: 'Signatures', icon: FileSignature, permission: 'document:approve', keywords: 'electronic signing requests' },
      { to: '/onboarding', label: 'Onboarding', icon: UserPlus, permissionAny: ['onboarding:self', 'onboarding:create', 'onboarding:assign'], keywords: 'new hires checklist templates assignments' },
    ],
  },
  {
    label: 'Administration',
    links: [
      { to: '/organizations', label: 'Organizations', icon: Building2, role: 'SUPER_ADMIN', keywords: 'tenants clients companies' },
      { to: '/users', label: 'Access & users', icon: Users, permission: 'user:read', keywords: 'accounts roles permissions' },
      { to: '/settings/employee-experience', label: 'Employee experience', icon: Sparkles, roles: ['SUPER_ADMIN', 'ORGANIZATION_OWNER', 'CLIENT_ADMIN'], keywords: 'homepage branding events' },
      { to: '/settings/employment-governance', label: 'Employment governance', icon: Briefcase, roles: ['SUPER_ADMIN', 'ORGANIZATION_OWNER', 'CLIENT_ADMIN'], keywords: 'job titles duplicate roles organization governance' },
      { to: '/settings', label: 'Settings', icon: Settings, keywords: 'security account preferences' },
      { to: '/help', label: 'Help center', icon: LifeBuoy, keywords: 'support guide help demo' },
    ],
  },
];

export function canViewNavigationItem(
  item,
  {
    hasPermission,
    hasRole,
    hasEmployeeProfile = false,
  },
) {
  return (
    (!item.permission || hasPermission(item.permission))
    && (!item.permissionAny || item.permissionAny.some(hasPermission))
    && (!item.role || hasRole(item.role))
    && (!item.roles || item.roles.some(hasRole))
    && (!item.requiresEmployeeProfile || hasEmployeeProfile)
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
  '/goals': 'Goals & KPIs',
  '/documents': 'Files',
  '/signature-requests': 'Signatures',
  '/tasks': 'Tasks',
  '/onboarding': 'Onboarding',
  '/leave/setup': 'Time-off setup',
  '/help': 'Help center',
  '/users': 'Access & users',
  '/organizations': 'Organizations',
  '/settings': 'Settings',
  '/settings/employee-experience': 'Employee experience',
  '/settings/employment-governance': 'Employment governance',
};

export function getPageTitle(pathname) {
  if (pathname.startsWith('/employees/')) return 'Employee profile';
  if (pathname.startsWith('/events/')) return 'Event';
  return pageTitles[pathname] || 'Kinetic';
}
