import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext.jsx';
import Login from '../pages/Login.jsx';

test('renders login form', () => {
  render(
    <MemoryRouter>
      <AuthContext.Provider value={{ user: null, login: vi.fn(), loading: false }}>
        <Login />
      </AuthContext.Provider>
    </MemoryRouter>,
  );
  expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
});
