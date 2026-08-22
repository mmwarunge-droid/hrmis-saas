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
    shareAccessLink: vi.fn(),
    sharePasswordResetBulk: vi.fn(),
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
      tenant_id: null,
      roles: ['SUPER_ADMIN'],
      permissions: ['user:create', 'user:read', 'user:update'],
    },
  });
  useTenant.mockReturnValue({ tenantId: null });
  usePermissions.mockReturnValue({
    hasRole: (role) => role === 'SUPER_ADMIN',
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
  userApi.sharePasswordResetBulk.mockResolvedValue({
    data: {
      requested: 1,
      sent: 1,
      skipped: 0,
      failed: 0,
      skipped_reasons: {
        not_found: 0,
        inactive: 0,
        awaiting_activation: 0,
        platform_account: 0,
      },
    },
  });

  userApi.shareAccessLink.mockImplementation((userId) => (
    Promise.resolve({
      data: {
        link_type: userId === 'user-invited'
          ? 'invitation'
          : 'password_reset',
        delivery: 'sent',
      },
    })
  ));
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



test('super admin sends password resets to selected active users', async () => {
  userApi.list.mockResolvedValue({
    data: {
      items: [
        {
          ...account(1),
          id: 'active-selected',
          full_name: 'Selected Active User',
          email: 'selected-active@example.test',
          account_status: 'active',
          activation_required: false,
          is_active: true,
        },
        {
          ...account(2),
          id: 'invited-not-eligible',
          full_name: 'Invited Not Eligible',
          email: 'invited-not-eligible@example.test',
          account_status: 'invited',
          activation_required: true,
          is_active: true,
        },
        {
          ...account(3),
          id: 'inactive-not-eligible',
          full_name: 'Inactive Not Eligible',
          email: 'inactive-not-eligible@example.test',
          account_status: 'inactive',
          activation_required: false,
          is_active: false,
        },
      ],
      meta: {
        page: 1,
        per_page: 15,
        total: 3,
        pages: 1,
      },
    },
  });

  render(
    <MemoryRouter>
      <Users />
    </MemoryRouter>,
  );

  await screen.findByText('Selected Active User');

  const activeCheckbox = screen.getByRole('checkbox', {
    name: 'Select Selected Active User for password reset',
  });
  const invitedCheckbox = screen.getByRole('checkbox', {
    name: 'Select Invited Not Eligible for password reset',
  });
  const inactiveCheckbox = screen.getByRole('checkbox', {
    name: 'Select Inactive Not Eligible for password reset',
  });

  expect(activeCheckbox).toBeEnabled();
  expect(invitedCheckbox).toBeDisabled();
  expect(inactiveCheckbox).toBeDisabled();

  fireEvent.click(activeCheckbox);

  fireEvent.click(
    screen.getByRole('button', {
      name: 'Send reset links (1)',
    }),
  );

  expect(
    await screen.findByText(
      'Send password reset links to 1 selected active user?',
    ),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole('button', {
      name: 'Confirm reset links',
    }),
  );

  await waitFor(() => {
    expect(userApi.sharePasswordResetBulk).toHaveBeenCalledWith({
      user_ids: ['active-selected'],
    });
  });

  expect(
    await screen.findByText('1 password reset link sent.'),
  ).toBeInTheDocument();
});


test('super admin sends password resets to an explicitly selected organization', async () => {
  tenantApi.options.mockResolvedValue({
    data: {
      items: [
        {
          id: 'tenant-1',
          name: 'Dundaa Labs',
        },
      ],
    },
  });

  render(
    <MemoryRouter>
      <Users />
    </MemoryRouter>,
  );

  await screen.findByText('Showing 15 of 35 matching accounts');

  fireEvent.change(
    screen.getByLabelText('Filter users by organization'),
    {
      target: {
        value: 'tenant-1',
      },
    },
  );

  const organizationButton = await screen.findByRole(
    'button',
    {
      name: 'Send reset links to Dundaa Labs',
    },
  );

  fireEvent.click(organizationButton);

  expect(
    await screen.findByText(
      'Send password reset links to all eligible active users in Dundaa Labs? Invited and inactive accounts will be skipped.',
    ),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole('button', {
      name: 'Confirm reset links',
    }),
  );

  await waitFor(() => {
    expect(userApi.sharePasswordResetBulk).toHaveBeenCalledWith({
      tenant_id: 'tenant-1',
    });
  });
});


test('shares invite and reset links from platform user management', async () => {
  userApi.list.mockResolvedValue({
    data: {
      items: [
        {
          ...account(1),
          id: 'user-invited',
          full_name: 'Invited Account',
          email: 'invited-account@example.test',
          account_status: 'invited',
          is_active: true,
        },
        {
          ...account(2),
          id: 'user-active',
          full_name: 'Active Account',
          email: 'active-account@example.test',
          account_status: 'active',
          is_active: true,
        },
        {
          ...account(3),
          id: 'user-suspended',
          full_name: 'Suspended Account',
          email: 'suspended-account@example.test',
          account_status: 'suspended',
          is_active: false,
        },
      ],
      meta: {
        page: 1,
        per_page: 15,
        total: 3,
        pages: 1,
      },
    },
  });

  render(
    <MemoryRouter>
      <Users />
    </MemoryRouter>,
  );

  await screen.findByText('Invited Account');

  const inviteButton = screen.getByRole(
    'button',
    { name: 'Share invite link with Invited Account' },
  );
  const resetButton = screen.getByRole(
    'button',
    { name: 'Share reset link with Active Account' },
  );

  expect(inviteButton).toHaveTextContent('Share Invite Link');
  expect(resetButton).toHaveTextContent('Share Reset Link');

  expect(
    screen.queryByRole(
      'button',
      { name: /share .* link with suspended account/i },
    ),
  ).not.toBeInTheDocument();

  fireEvent.click(inviteButton);

  await waitFor(() => {
    expect(userApi.shareAccessLink).toHaveBeenCalledWith(
      'user-invited',
    );
  });

  expect(
    await screen.findByText(
      'A new activation invitation was sent to invited-account@example.test.',
    ),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole(
      'button',
      { name: 'Share reset link with Active Account' },
    ),
  );

  await waitFor(() => {
    expect(userApi.shareAccessLink).toHaveBeenCalledWith(
      'user-active',
    );
  });

  expect(
    await screen.findByText(
      'A password reset link was sent to active-account@example.test.',
    ),
  ).toBeInTheDocument();
});
