import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  MemoryRouter,
  Route,
  Routes,
} from 'react-router-dom';
import { authApi } from '../api/authApi';
import EmployeeAccessForm from '../components/employees/EmployeeAccessForm.jsx';
import OrganizationProvisionForm from '../components/organizations/OrganizationProvisionForm.jsx';
import UserProvisionForm from '../components/users/UserProvisionForm.jsx';
import ActivateAccount from '../pages/ActivateAccount.jsx';

vi.mock('../api/authApi', () => ({
  authApi: {
    validateInvitation: vi.fn(),
    acceptInvitation: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

test('invitee validates the link, creates a private password and reaches login', async () => {
  authApi.validateInvitation.mockResolvedValue({
    data: {
      full_name: 'Jane Doe',
      first_name: 'Jane',
      email: 'jane@example.com',
      organization_name: 'Kinetic Demo Group',
      expires_at: '2026-08-12T12:00:00',
    },
  });
  authApi.acceptInvitation.mockResolvedValue({
    data: { email: 'jane@example.com' },
  });
  const user = userEvent.setup();

  render(
    <MemoryRouter
      initialEntries={['/activate-account#token=secure-account-invite-token-value']}
    >
      <Routes>
        <Route path="/activate-account" element={<ActivateAccount />} />
        <Route path="/login" element={<div>Sign in destination</div>} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText('jane@example.com')).toBeInTheDocument();
  expect(authApi.validateInvitation).toHaveBeenCalledWith({
    token: 'secure-account-invite-token-value',
  });

  await user.type(
    screen.getByLabelText(/^new password$/i),
    'PrivateInvitePass456!',
  );
  await user.type(
    screen.getByLabelText(/^confirm password$/i),
    'PrivateInvitePass456!',
  );
  await user.click(
    screen.getByRole('button', { name: /activate my account/i }),
  );

  await waitFor(() => expect(authApi.acceptInvitation).toHaveBeenCalledWith({
    token: 'secure-account-invite-token-value',
    password: 'PrivateInvitePass456!',
  }));
  expect(await screen.findByText('Sign in destination')).toBeInTheDocument();
});

test('administrative provisioning forms no longer ask for another user password', async () => {
  const user = userEvent.setup();
  const noop = vi.fn();
  const { unmount } = render(
    <UserProvisionForm onSubmit={noop} />,
  );
  expect(
    screen.queryByLabelText(/temporary password/i),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(/user creates their own private password/i),
  ).toBeInTheDocument();
  unmount();

  const employeeSubmit = vi.fn();
  const employee = {
    full_name: 'Jane Doe',
    email: 'jane@example.com',
  };
  const employeeRender = render(
    <EmployeeAccessForm employee={employee} onSubmit={employeeSubmit} />,
  );
  expect(
    screen.queryByLabelText(/temporary password/i),
  ).not.toBeInTheDocument();
  await user.click(
    screen.getByRole('button', { name: /provision access/i }),
  );
  expect(employeeSubmit).toHaveBeenCalledTimes(1);
  expect(employeeSubmit.mock.calls[0][0].roles).toEqual(['EMPLOYEE']);
  expect(employeeSubmit.mock.calls[0][0]).not.toHaveProperty('password');
  employeeRender.unmount();

  render(<OrganizationProvisionForm onSubmit={noop} />);
  expect(
    screen.queryByLabelText(/temporary password/i),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(/administrator a secure activation link/i),
  ).toBeInTheDocument();
});
