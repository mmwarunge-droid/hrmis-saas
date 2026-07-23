import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { authApi } from '../api/authApi';
import ForgotPassword from '../pages/ForgotPassword.jsx';
import ResetPassword from '../pages/ResetPassword.jsx';
import VerifyEmail from '../pages/VerifyEmail.jsx';

vi.mock('../api/authApi', () => ({
  authApi: {
    forgotPassword: vi.fn(),
    resetPassword: vi.fn(),
    confirmEmailVerification: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

test('submits an enumeration-safe password reset request', async () => {
  authApi.forgotPassword.mockResolvedValue({ message: 'If the account exists, password reset instructions will be sent' });
  const user = userEvent.setup();
  render(<MemoryRouter><ForgotPassword /></MemoryRouter>);

  await user.type(screen.getByLabelText(/email/i), 'employee@example.com');
  await user.click(screen.getByRole('button', { name: /send reset link/i }));

  await waitFor(() => expect(authApi.forgotPassword).toHaveBeenCalledWith({ email: 'employee@example.com' }));
  expect(screen.getByText(/if the account exists/i)).toBeInTheDocument();
});

test('submits the reset token and matching new password', async () => {
  authApi.resetPassword.mockResolvedValue({ message: 'Password reset completed' });
  const user = userEvent.setup();
  render(<MemoryRouter initialEntries={['/reset-password#token=one-time-token-value']}><ResetPassword /></MemoryRouter>);

  await user.type(screen.getByLabelText(/^new password$/i), 'DifferentStrongPass456!');
  await user.type(screen.getByLabelText(/confirm password/i), 'DifferentStrongPass456!');
  await user.click(screen.getByRole('button', { name: /reset password/i }));

  await waitFor(() => expect(authApi.resetPassword).toHaveBeenCalledWith({
    token: 'one-time-token-value',
    password: 'DifferentStrongPass456!',
  }));
  expect(screen.getByText(/password reset completed/i)).toBeInTheDocument();
});

test('requires an explicit action before confirming email verification', async () => {
  authApi.confirmEmailVerification.mockResolvedValue({ message: 'Email address verified' });
  render(<MemoryRouter initialEntries={['/verify-email#token=email-token-value']}><VerifyEmail /></MemoryRouter>);

  expect(authApi.confirmEmailVerification).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: /verify email/i }));

  await waitFor(() => expect(authApi.confirmEmailVerification).toHaveBeenCalledWith({ token: 'email-token-value' }));
  expect(screen.getByText(/email address verified/i)).toBeInTheDocument();
});
