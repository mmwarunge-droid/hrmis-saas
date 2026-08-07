import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { tenantApi } from '../api/tenantApi.js';
import { userApi } from '../api/userApi.js';
import useAuth from '../hooks/useAuth.js';
import usePermissions from '../hooks/usePermissions.js';
import useTenant from '../hooks/useTenant.js';
import Users from '../pages/Users.jsx';

vi.mock('../api/tenantApi.js', () => ({
  tenantApi: {
    options: vi.fn(),
  },
}));

vi.mock('../api/userApi.js', () => ({
  userApi: {
    list: vi.fn(),
    summary: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    updateRoles: vi.fn(),
  },
}));

vi.mock('../hooks/useAuth.js', () => ({
  default: vi.fn(),
}));

vi.mock('../hooks/usePermissions.js', () => ({
  default: vi.fn(),
}));

vi.mock('../hooks/useTenant.js', () => ({
  default: vi.fn(),
}));

function account(index) {
  return {
    id: `user-${index}`,
    tenant_id: 'tenant-1',
    first_name: 'Account',
    last_name: String(index).padStart(2, '0'),
    full_name: `Account ${String(index).padStart(2, '0')}`,
    email: `account-${index}@example.test`,
    roles: ['EMPLOYEE'],
    email_verified: index <= 20,
    mfa_enabled: index <= 8,
    is_active: index !== 35,
    last_login_at: '2026-08-01T09:00:00',
  };
}

beforeEach(() => {
  vi.clearAllMocks();

  useAuth.mockReturnValue({
    user: {
      id: 'admin-user',
      tenant_id: 'tenant-1',
      roles: ['CLIENT_ADMIN'],
      permissions: ['user:create', 'user:read', 'user:update'],
    },
  });
  useTenant.mockReturnValue({ tenantId: 'tenant-1' });
  usePermissions.mockReturnValue({
    hasRole: () => false,
    hasPermission: (permission) => [
      'user:create',
      'user:update',
    ].includes(permission),
  });

  tenantApi.options.mockResolvedValue({ data: { items: [] } });
  userApi.summary.mockResolvedValue({
    data: {
      total: 35,
      active: 34,
      verified: 20,
      mfa_enabled: 8,
      privileged: 1,
    },
  });
  userApi.list.mockImplementation((params) => {
    const page = params.page || 1;
    const start = ((page - 1) * 15) + 1;
    return Promise.resolve({
      data: {
        items: Array.from(
          { length: page === 3 ? 5 : 15 },
          (_, offset) => account(start + offset),
        ),
        meta: {
          page,
          per_page: 15,
          total: 35,
          pages: 3,
        },
      },
    });
  });
  userApi.update.mockResolvedValue({
    data: { ...account(1), is_active: false, revoked_sessions: 2 },
  });
  userApi.updateRoles.mockResolvedValue({ data: account(1) });
});

test('uses complete user totals and server-side directory controls', async () => {
  render(
    <MemoryRouter>
      <Users />
    </MemoryRouter>,
  );

  expect(
    await screen.findByText('Showing 15 of 35 matching accounts'),
  ).toBeInTheDocument();
  expect(screen.getByText('1–15 of 35 user accounts')).toBeInTheDocument();
  expect(screen.getByText('Complete identity scope').closest('section'))
    .toHaveTextContent('35');
  expect(screen.getByText('Privileged users').closest('section'))
    .toHaveTextContent('1');

  fireEvent.click(screen.getByRole('button', { name: /next page/i }));
  await waitFor(() => {
    expect(userApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2, per_page: 15 }),
    );
  });

  fireEvent.change(screen.getByLabelText('Search user accounts'), {
    target: { value: 'account 35' },
  });
  await waitFor(() => {
    expect(userApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, q: 'account 35' }),
    );
  });

  fireEvent.change(screen.getByLabelText('Filter users by status'), {
    target: { value: 'inactive' },
  });
  await waitFor(() => {
    expect(userApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'inactive' }),
    );
  });

  fireEvent.click(screen.getByRole('button', { name: 'Person' }));
  await waitFor(() => {
    expect(userApi.list).toHaveBeenCalledWith(
      expect.objectContaining({
        sort: 'full_name',
        direction: 'desc',
      }),
    );
  });
});

test('updates account lifecycle status and roles from the management dialog', async () => {
  render(
    <MemoryRouter>
      <Users />
    </MemoryRouter>,
  );

  await screen.findByText('Showing 15 of 35 matching accounts');
  fireEvent.click(
    screen.getByRole('button', { name: 'Manage Account 01' }),
  );

  const accountStatus = await screen.findByLabelText('Account status');
  fireEvent.change(accountStatus, {
    target: { value: 'inactive' },
  });
  fireEvent.click(screen.getByLabelText('MANAGER'));
  fireEvent.click(screen.getByRole('button', { name: 'Save account' }));

  await waitFor(() => {
    expect(userApi.update).toHaveBeenCalledWith(
      'user-1',
      expect.objectContaining({
        first_name: 'Account',
        last_name: '01',
        is_active: false,
      }),
    );
    expect(userApi.updateRoles).toHaveBeenCalledWith(
      'user-1',
      expect.arrayContaining(['EMPLOYEE', 'MANAGER']),
    );
  });

  expect(
    await screen.findByText('Account updated and 2 active sessions revoked.'),
  ).toBeInTheDocument();
});
