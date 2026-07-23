import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { authApi } from '../api/authApi';
import { AuthContext } from '../context/AuthContext.jsx';
import MfaChallenge from '../pages/MfaChallenge.jsx';

vi.mock('../api/authApi', () => ({
  authApi: {
    startMfaEnrollment: vi.fn(),
  },
}));

beforeEach(() => vi.clearAllMocks());

function renderChallenge({ enrollmentRequired = false, confirm = vi.fn(), verify = vi.fn() } = {}) {
  return render(
    <MemoryRouter initialEntries={[{
      pathname: '/mfa',
      state: { challengeToken: 'short-lived-challenge', enrollmentRequired, destination: '/dashboard' },
    }]}>
      <AuthContext.Provider value={{ user: null, confirmMfaEnrollment: confirm, verifyMfaChallenge: verify }}>
        <Routes><Route path="/mfa" element={<MfaChallenge />} /><Route path="/dashboard" element={<p>Dashboard</p>} /></Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

test('verifies a login MFA challenge without persisting the challenge token', async () => {
  const verify = vi.fn().mockResolvedValue({ user: { email: 'admin@example.com' } });
  const storageWrite = vi.spyOn(Storage.prototype, 'setItem');
  const user = userEvent.setup();
  renderChallenge({ verify });

  await user.type(screen.getByLabelText(/authenticator or recovery code/i), '123456');
  await user.click(screen.getByRole('button', { name: /^verify$/i }));

  await waitFor(() => expect(verify).toHaveBeenCalledWith({ challenge_token: 'short-lived-challenge', code: '123456' }));
  expect(storageWrite).not.toHaveBeenCalled();
});

test('starts enrollment and confirms the first authenticator code', async () => {
  authApi.startMfaEnrollment.mockResolvedValue({
    data: { manual_key: 'BASE32SECRET', qr_code_data_uri: 'data:image/svg+xml;base64,PHN2Zz4=' },
  });
  const confirm = vi.fn().mockResolvedValue({ user: { email: 'admin@example.com' }, recovery_codes: ['ABCD-EFGH-JKLM'] });
  const user = userEvent.setup();
  renderChallenge({ enrollmentRequired: true, confirm });

  expect(await screen.findByAltText(/authenticator qr code/i)).toBeInTheDocument();
  expect(screen.getByText('BASE32SECRET')).toBeInTheDocument();
  await user.type(screen.getByLabelText(/six-digit authenticator code/i), '654321');
  await user.click(screen.getByRole('button', { name: /enable mfa/i }));

  await waitFor(() => expect(confirm).toHaveBeenCalledWith({ challenge_token: 'short-lived-challenge', code: '654321' }));
  expect(await screen.findByText('ABCD-EFGH-JKLM')).toBeInTheDocument();
});
