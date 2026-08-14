import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext.jsx';
import Login from '../pages/Login.jsx';

function renderLogin(overrides = {}) {
  render(
    <MemoryRouter>
      <AuthContext.Provider
        value={{
          user: null,
          login: vi.fn(),
          loading: false,
          sessionMessage: '',
          ...overrides,
        }}
      >
        <Login />
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

test('renders login form', () => {
  renderLogin();
  expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
});

test('shows and hides the password without changing its value', async () => {
  const user = userEvent.setup();
  renderLogin();

  const password = screen.getByLabelText('Password');
  await user.type(password, 'KineticDemoPass!');

  expect(password).toHaveAttribute('type', 'password');
  await user.click(screen.getByRole('button', { name: 'Show password' }));
  expect(password).toHaveAttribute('type', 'text');
  expect(password).toHaveValue('KineticDemoPass!');

  await user.click(screen.getByRole('button', { name: 'Hide password' }));
  expect(password).toHaveAttribute('type', 'password');
});

test('shows a friendly session-expired message without token terminology', () => {
  renderLogin({ sessionMessage: 'Your session has expired. Please sign in again.' });

  expect(screen.getByText('Your session has expired. Please sign in again.')).toBeInTheDocument();
  expect(screen.queryByText(/token has expired/i)).not.toBeInTheDocument();
});
