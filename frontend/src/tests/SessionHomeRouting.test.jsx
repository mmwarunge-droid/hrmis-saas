import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Login from '../pages/Login.jsx';
import PermissionRoute from '../routes/PermissionRoute.jsx';
import ProtectedRoute from '../routes/ProtectedRoute.jsx';
import useAuth from '../hooks/useAuth';
import usePermissions from '../hooks/usePermissions.js';

vi.mock('../hooks/useAuth');
vi.mock('../hooks/usePermissions.js');

function MfaState() {
  const location = useLocation();
  return <div>MFA destination: {location.state?.destination || 'none'}</div>;
}

describe('session home routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends a newly authenticated user to their role-aware homepage, not a stale route', async () => {
    const login = vi.fn().mockResolvedValue({
      mfa_required: false,
      user: { id: 'employee-1' },
    });
    useAuth.mockReturnValue({ user: null, login });

    render(
      <MemoryRouter
        initialEntries={[{
          pathname: '/login',
          state: { from: { pathname: '/departments' } },
        }]}
      >
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<div>Own homepage</div>} />
          <Route path="/departments" element={<div>Stale administrator page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Work email'), {
      target: { value: 'employee@example.test' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'StrongPass123!' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Sign in/i }));

    expect(await screen.findByText('Own homepage')).toBeInTheDocument();
    expect(screen.queryByText('Stale administrator page')).not.toBeInTheDocument();
    expect(login).toHaveBeenCalled();
  });

  it('carries the homepage destination through MFA', async () => {
    const login = vi.fn().mockResolvedValue({
      mfa_required: true,
      challenge_token: 'challenge',
      mfa_enrollment_required: false,
    });
    useAuth.mockReturnValue({ user: null, login });

    render(
      <MemoryRouter
        initialEntries={[{
          pathname: '/login',
          state: { from: { pathname: '/departments' } },
        }]}
      >
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/mfa" element={<MfaState />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Work email'), {
      target: { value: 'employee@example.test' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'StrongPass123!' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Sign in/i }));

    expect(await screen.findByText('MFA destination: /dashboard')).toBeInTheDocument();
  });

  it('redirects an authenticated user away from a route they are not permitted to open', async () => {
    useAuth.mockReturnValue({
      user: { id: 'employee-1', roles: ['EMPLOYEE'] },
      loading: false,
    });
    usePermissions.mockReturnValue({
      hasPermission: () => false,
    });

    render(
      <MemoryRouter initialEntries={['/departments']}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route element={<PermissionRoute permission="employee:update" />}>
              <Route path="/departments" element={<div>Departments administration</div>} />
            </Route>
            <Route path="/dashboard" element={<div>Own homepage</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Own homepage')).toBeInTheDocument();
    });
    expect(screen.queryByText('Departments administration')).not.toBeInTheDocument();
  });
});
