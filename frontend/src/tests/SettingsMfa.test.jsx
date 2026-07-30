import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthContext } from '../context/AuthContext.jsx';
import { authApi } from '../api/authApi.js';
import Settings from '../pages/Settings.jsx';

vi.mock('../api/authApi.js', () => ({
  authApi: {
    mfaStatus: vi.fn(),
    requestEmailVerification: vi.fn(),
    startSelfMfaEnrollment: vi.fn(),
    confirmSelfMfaEnrollment: vi.fn(),
    regenerateMfaRecoveryCodes: vi.fn(),
    disableMfa: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  authApi.mfaStatus.mockResolvedValue({
    data: {
      enabled: false,
      required: false,
      email_verified: true,
      recovery_codes_remaining: 0,
      recovery_codes_low: false,
      policy: {
        can_disable: true,
        in_grace_period: false,
      },
    },
  });
});

test('employee enrolls an authenticator from settings with a QR code', async () => {
  authApi.startSelfMfaEnrollment.mockResolvedValue({
    data: {
      challenge_token: 'self-enrollment-challenge',
      manual_key: 'BASE32SECRET',
      qr_code_data_uri: 'data:image/svg+xml;base64,PHN2Zz4=',
    },
  });
  authApi.confirmSelfMfaEnrollment.mockResolvedValue({
    message: 'Multi-factor authentication enabled',
    data: {
      mfa: {
        enabled: true,
        required: false,
        email_verified: true,
        recovery_codes_remaining: 2,
        recovery_codes_low: true,
        policy: { can_disable: true },
      },
      recovery_codes: ['AAAA-BBBB-CCCC', 'DDDD-EEEE-FFFF'],
    },
  });

  const user = userEvent.setup();
  render(
    <AuthContext.Provider value={{
      user: {
        id: 'user-1',
        tenant_id: 'tenant-1',
        email_verified: true,
      },
    }}>
      <Settings />
    </AuthContext.Provider>,
  );

  await screen.findByRole('button', {
    name: /set up authenticator/i,
  });
  await user.type(
    screen.getByLabelText(/current password/i),
    'StrongPass123!',
  );
  await user.click(screen.getByRole('button', {
    name: /set up authenticator/i,
  }));

  expect(await screen.findByAltText(/authenticator qr code/i))
    .toBeInTheDocument();
  expect(screen.getByText('BASE32SECRET')).toBeInTheDocument();

  await user.type(
    screen.getByLabelText(/six-digit authenticator code/i),
    '123456',
  );
  await user.click(screen.getByRole('button', {
    name: /enable mfa/i,
  }));

  await waitFor(() => expect(
    authApi.confirmSelfMfaEnrollment,
  ).toHaveBeenCalledWith({
    challenge_token: 'self-enrollment-challenge',
    code: '123456',
  }));
  expect(await screen.findByText('AAAA-BBBB-CCCC'))
    .toBeInTheDocument();
  expect(screen.getByText(/authenticator mfa is enabled/i))
    .toBeInTheDocument();
});
