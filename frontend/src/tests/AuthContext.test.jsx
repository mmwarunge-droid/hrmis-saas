import { act, render, screen } from '@testing-library/react';
import { useContext } from 'react';
import { AuthContext, AuthProvider } from '../context/AuthContext.jsx';
import { authApi } from '../api/authApi.js';

vi.mock('../api/authApi.js', () => ({
  authApi: {
    me: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
}));

function Consumer() {
  const auth = useContext(AuthContext);
  return (
    <div>
      <span>{auth.loading ? 'loading' : auth.user?.email || 'anonymous'}</span>
      <button type="button" onClick={() => auth.login({ email: 'admin@example.com', password: 'secret' })}>
        Login
      </button>
      <button type="button" onClick={() => auth.logout()}>
        Logout
      </button>
    </div>
  );
}

test('uses server cookies without writing JWTs to localStorage', async () => {
  authApi.me.mockRejectedValueOnce({ error: { code: 'AUTHENTICATION_REQUIRED' } });
  authApi.login.mockResolvedValueOnce({ data: { user: { email: 'admin@example.com' } } });
  authApi.logout.mockResolvedValueOnce({ data: {} });
  const setItem = vi.spyOn(Storage.prototype, 'setItem');

  render(<AuthProvider><Consumer /></AuthProvider>);

  await screen.findByText('anonymous');
  await act(async () => { screen.getByRole('button', { name: 'Login' }).click(); });
  expect(await screen.findByText('admin@example.com')).toBeInTheDocument();
  expect(setItem).not.toHaveBeenCalled();

  await act(async () => { screen.getByRole('button', { name: 'Logout' }).click(); });
  expect(await screen.findByText('anonymous')).toBeInTheDocument();
});
