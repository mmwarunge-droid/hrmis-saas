import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext.jsx';
import ProtectedRoute from '../routes/ProtectedRoute.jsx';

test('renders protected content for authenticated user', () => {
  render(
    <MemoryRouter initialEntries={['/secure']}>
      <AuthContext.Provider value={{ user: { full_name: 'Admin' }, loading: false }}>
        <Routes><Route element={<ProtectedRoute />}><Route path="/secure" element={<p>Secure Area</p>} /></Route></Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
  expect(screen.getByText('Secure Area')).toBeInTheDocument();
});

test('redirects an unauthenticated user to login', () => {
  render(
    <MemoryRouter initialEntries={['/secure']}>
      <AuthContext.Provider value={{ user: null, loading: false }}>
        <Routes>
          <Route element={<ProtectedRoute />}><Route path="/secure" element={<p>Secure Area</p>} /></Route>
          <Route path="/login" element={<p>Login Page</p>} />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  );

  expect(screen.getByText('Login Page')).toBeInTheDocument();
  expect(screen.queryByText('Secure Area')).not.toBeInTheDocument();
});
