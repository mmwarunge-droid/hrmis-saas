import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { employeeApi } from '../api/employeeApi.js';
import { tenantApi } from '../api/tenantApi.js';
import { userApi } from '../api/userApi.js';
import useAuth from '../hooks/useAuth.js';
import usePermissions from '../hooks/usePermissions.js';
import useTenant from '../hooks/useTenant.js';
import Users from '../pages/Users.jsx';

vi.mock('../api/employeeApi.js', () => ({
  employeeApi: {
    accessDirectory: vi.fn(),
    provisionAccess: vi.fn(),
    updateAccess: vi.fn(),
  },
}));

vi.mock('../api/tenantApi.js', () => ({
  tenantApi: { options: vi.fn() },
}));

vi.mock('../api/userApi.js', () => ({
  userApi: {
    list: vi.fn(),
    summary: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    updateRoles: vi.fn(),
    resendInvitation: vi.fn(),
  },
}));

vi.mock('../hooks/useAuth.js', () => ({ default: vi.fn() }));
vi.mock('../hooks/usePermissions.js', () => ({ default: vi.fn() }));
vi.mock('../hooks/useTenant.js', () => ({ default: vi.fn() }));

const employeeRows = [
  {
    id: 'emp-no-access',
    tenant_id: 'tenant-1',
    employee_number: 'EMP-001',
    full_name: 'No Access Employee',
    email: 'no-access@example.test',
    employment_status: 'active',
    access: null,
  },
  {
    id: 'emp-invited',
    tenant_id: 'tenant-1',
    employee_number: 'EMP-002',
    full_name: 'Invited Employee',
    email: 'invited@example.test',
    employment_status: 'active',
    access: {
      user_id: 'user-invited',
      status: 'invited',
      is_active: true,
      roles: ['EMPLOYEE'],
      invitation_sent_at: '2026-08-14T06:00:00',
      last_login_at: null,
    },
  },
  {
    id: 'emp-active',
    tenant_id: 'tenant-1',
    employee_number: 'EMP-003',
    full_name: 'Active Manager',
    email: 'active@example.test',
    employment_status: 'active',
    access: {
      user_id: 'user-active',
      status: 'active',
      is_active: true,
      roles: ['MANAGER'],
      invitation_sent_at: null,
      last_login_at: '2026-08-13T09:00:00',
    },
  },
  {
    id: 'emp-inactive',
    tenant_id: 'tenant-1',
    employee_number: 'EMP-004',
    full_name: 'Inactive Employee',
    email: 'inactive@example.test',
    employment_status: 'active',
    access: {
      user_id: 'user-inactive',
      status: 'suspended',
      is_active: false,
      roles: ['EMPLOYEE'],
      invitation_sent_at: null,
      last_login_at: null,
    },
  },
];

function clientAdminPermissions() {
  return {
    hasRole: () => false,
    hasPermission: (permission) => [
      'employee:read',
      'employee:update',
      'user:create',
      'user:read',
      'user:update',
    ].includes(permission),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuth.mockReturnValue({
    user: {
      id: 'client-admin',
      tenant_id: 'tenant-1',
      roles: ['CLIENT_ADMIN'],
    },
  });
  useTenant.mockReturnValue({ tenantId: 'tenant-1' });
  usePermissions.mockReturnValue(clientAdminPermissions());

  tenantApi.options.mockResolvedValue({ data: { items: [] } });
  userApi.summary.mockResolvedValue({
    data: {
      total: 3,
      active: 1,
      invited: 1,
      verified: 1,
      mfa_enabled: 0,
      privileged: 0,
    },
  });
  userApi.list.mockResolvedValue({
    data: {
      items: [],
      meta: { page: 1, per_page: 15, total: 0, pages: 1 },
    },
  });
  employeeApi.accessDirectory.mockResolvedValue({
    data: {
      items: employeeRows,
      meta: { page: 1, per_page: 15, total: 4, pages: 1 },
    },
  });
  employeeApi.provisionAccess.mockResolvedValue({
    data: { user: { id: 'user-new', account_status: 'invited' } },
  });
  employeeApi.updateAccess.mockResolvedValue({
    data: {
      access: {
        user_id: 'user-active',
        status: 'suspended',
        roles: ['MANAGER'],
      },
      revoked_sessions: 1,
    },
  });
  userApi.resendInvitation.mockResolvedValue({ data: {} });
});

test('client admin manages platform access from the existing employee directory', async () => {
  render(<MemoryRouter><Users /></MemoryRouter>);

  expect(await screen.findByText('No Access Employee')).toBeInTheDocument();
  expect(screen.getByText('Invited Employee')).toBeInTheDocument();
  expect(screen.getByText('Active Manager')).toBeInTheDocument();
  expect(screen.getByText('Inactive Employee')).toBeInTheDocument();

  const noAccessRow = screen.getByText('No Access Employee').closest('tr');
  const invitedRow = screen.getByText('Invited Employee').closest('tr');
  const activeRow = screen.getByText('Active Manager').closest('tr');
  const inactiveRow = screen.getByText('Inactive Employee').closest('tr');

  expect(within(noAccessRow).getByText('No access')).toBeInTheDocument();
  expect(within(invitedRow).getByText('Invited')).toBeInTheDocument();
  expect(within(activeRow).getByText('Active')).toBeInTheDocument();
  expect(within(inactiveRow).getByText('Inactive')).toBeInTheDocument();

  expect(employeeApi.accessDirectory).toHaveBeenCalledWith(
    expect.objectContaining({ page: 1, per_page: 15 }),
  );
  expect(userApi.list).not.toHaveBeenCalled();
  expect(
    screen.queryByRole('button', { name: /create user/i }),
  ).not.toBeInTheDocument();

  fireEvent.click(
    screen.getByRole('button', { name: 'Grant access to No Access Employee' }),
  );
  expect(
    await screen.findByText('Provision access for No Access Employee'),
  ).toBeInTheDocument();
  expect(screen.queryByLabelText(/first name/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/last name/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/work email/i)).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText(/access role/i), {
    target: { value: 'MANAGER' },
  });
  fireEvent.click(screen.getByRole('button', { name: /provision access/i }));

  await waitFor(() => {
    expect(employeeApi.provisionAccess).toHaveBeenCalledWith(
      'emp-no-access',
      { roles: ['MANAGER'] },
    );
  });
});

test('client admin can deactivate access without editing employee identity', async () => {
  render(<MemoryRouter><Users /></MemoryRouter>);

  await screen.findByText('Active Manager');
  fireEvent.click(
    screen.getByRole('button', { name: 'Manage access for Active Manager' }),
  );

  expect(screen.queryByLabelText(/first name/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/last name/i)).not.toBeInTheDocument();

  fireEvent.change(
    await screen.findByLabelText('Platform access'),
    { target: { value: 'inactive' } },
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save access' }));

  await waitFor(() => {
    expect(employeeApi.updateAccess).toHaveBeenCalledWith(
      'emp-active',
      { roles: ['MANAGER'], is_active: false },
    );
  });
});

test('super admin retains the platform-user provisioning workflow', async () => {
  useAuth.mockReturnValue({
    user: { id: 'super-admin', tenant_id: null, roles: ['SUPER_ADMIN'] },
  });
  useTenant.mockReturnValue({ tenantId: null });
  usePermissions.mockReturnValue({
    hasRole: (role) => role === 'SUPER_ADMIN',
    hasPermission: () => true,
  });
  userApi.list.mockResolvedValue({
    data: {
      items: [{
        id: 'platform-user',
        tenant_id: 'tenant-1',
        full_name: 'Platform User',
        email: 'platform-user@example.test',
        roles: ['CLIENT_ADMIN'],
        is_active: true,
        account_status: 'active',
      }],
      meta: { page: 1, per_page: 15, total: 1, pages: 1 },
    },
  });

  render(<MemoryRouter><Users /></MemoryRouter>);

  expect(await screen.findByText('Platform users')).toBeInTheDocument();
  expect(
    screen.getByRole('button', { name: /create user/i }),
  ).toBeInTheDocument();
  expect(userApi.list).toHaveBeenCalled();
  expect(employeeApi.accessDirectory).not.toHaveBeenCalled();
});
