import {
  getPageTitle,
  navigationGroups,
  visibleNavigation,
} from '../config/navigation.js';

function labels(groups) {
  return groups.flatMap((group) => group.links.map((item) => item.label));
}

test('keeps universal work destinations available without elevated permissions', () => {
  const visible = visibleNavigation(navigationGroups, {
    hasPermission: () => false,
    hasRole: () => false,
  });

  expect(labels(visible)).toEqual(expect.arrayContaining([
    'My tasks',
    'Ask Kinetic',
    'Settings',
  ]));
});

test('shows people and administration destinations only when authorized', () => {
  const permissions = new Set(['employee:read', 'employee:update', 'user:read']);
  const roles = new Set(['CLIENT_ADMIN']);
  const visible = visibleNavigation(navigationGroups, {
    hasPermission: (permission) => permissions.has(permission),
    hasRole: (role) => roles.has(role),
  });

  expect(labels(visible)).toEqual(expect.arrayContaining([
    'People',
    'Org chart',
    'Departments',
    'Access & users',
    'Employee experience',
    'Employment governance',
  ]));
  expect(labels(visible)).not.toContain('Organizations');
});

test('uses the employment governance page title', () => {
  expect(
    getPageTitle('/settings/employment-governance'),
  ).toBe('Employment governance');
});

test('shows My info to a client administrator who is also an employee', () => {
  const roles = new Set(['CLIENT_ADMIN']);

  const visible = visibleNavigation(navigationGroups, {
    hasPermission: () => false,
    hasRole: (role) => roles.has(role),
    hasEmployeeProfile: true,
  });

  expect(labels(visible)).toContain('My info');
});


test('hides My info when the authenticated user has no employee profile', () => {
  const roles = new Set(['EMPLOYEE']);

  const visible = visibleNavigation(navigationGroups, {
    hasPermission: () => false,
    hasRole: (role) => roles.has(role),
    hasEmployeeProfile: false,
  });

  expect(labels(visible)).not.toContain('My info');
});
