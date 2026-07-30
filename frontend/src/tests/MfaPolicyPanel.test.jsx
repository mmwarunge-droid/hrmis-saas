import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { tenantApi } from '../api/tenantApi.js';
import MfaPolicyPanel from '../components/security/MfaPolicyPanel.jsx';

vi.mock('../api/tenantApi.js', () => ({
  tenantApi: {
    mfaPolicy: vi.fn(),
    updateMfaPolicy: vi.fn(),
    mfaCompliance: vi.fn(),
  },
}));

vi.mock('../api/userApi.js', () => ({
  userApi: {
    resetMfa: vi.fn(),
  },
}));

const policy = {
  tenant_id: 'tenant-1',
  mode: 'optional',
  grace_days: 14,
  enforcement_date: null,
  modes: [
    {
      value: 'optional',
      label: 'Optional',
      description: 'Employees may enroll voluntarily.',
    },
    {
      value: 'all_users',
      label: 'All users',
      description: 'Require MFA for every active user.',
    },
  ],
};

const compliance = {
  policy,
  summary: {
    total_users: 2,
    required_users: 0,
    enabled_users: 1,
    noncompliant_users: 0,
  },
  items: [
    {
      id: 'admin-1',
      full_name: 'Admin User',
      email: 'admin@example.test',
      roles: ['CLIENT_ADMIN'],
      mfa_enabled: true,
      compliant: true,
      required: false,
      in_grace_period: false,
      enforcement_date: null,
    },
    {
      id: 'employee-1',
      full_name: 'Employee User',
      email: 'employee@example.test',
      roles: ['EMPLOYEE'],
      mfa_enabled: false,
      compliant: true,
      required: false,
      in_grace_period: false,
      enforcement_date: null,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  tenantApi.mfaPolicy.mockResolvedValue({ data: policy });
  tenantApi.mfaCompliance.mockResolvedValue({
    data: compliance,
  });
});

test('administrator schedules tenant-wide MFA enforcement', async () => {
  tenantApi.updateMfaPolicy.mockResolvedValue({
    message: 'MFA policy updated',
    data: {
      ...policy,
      mode: 'all_users',
      grace_days: 30,
      enforcement_date: '2026-08-29',
    },
  });

  const user = userEvent.setup();
  render(
    <MfaPolicyPanel
      tenantId="tenant-1"
      currentUserId="admin-1"
    />,
  );

  const mode = await screen.findByLabelText(/policy mode/i);
  await user.selectOptions(mode, 'all_users');

  const grace = screen.getByLabelText(/enrollment grace days/i);
  await user.clear(grace);
  await user.type(grace, '30');

  const date = screen.getByLabelText(/enforcement date/i);
  await user.type(date, '2026-08-29');

  await user.click(screen.getByRole('button', {
    name: /save mfa policy/i,
  }));

  await waitFor(() => expect(
    tenantApi.updateMfaPolicy,
  ).toHaveBeenCalledWith(
    'tenant-1',
    {
      mode: 'all_users',
      grace_days: 30,
      enforcement_date: '2026-08-29',
    },
  ));
  expect(await screen.findByText('MFA policy updated'))
    .toBeInTheDocument();
});
