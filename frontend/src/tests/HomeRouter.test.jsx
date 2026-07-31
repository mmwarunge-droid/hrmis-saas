import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import HomeRouter from '../pages/HomeRouter.jsx';
import usePermissions from '../hooks/usePermissions.js';

vi.mock('../hooks/usePermissions.js');
vi.mock('../pages/Dashboard.jsx', () => ({ default: () => <div>Administrator dashboard</div> }));
vi.mock('../pages/EmployeeHome.jsx', () => ({ default: () => <div>Employee welcome home</div> }));

function permissions(roles) {
  return {
    hasAnyRole: (allowed) => allowed.some((role) => roles.includes(role)),
  };
}

describe('HomeRouter', () => {
  it('shows the welcoming homepage to employees', () => {
    usePermissions.mockReturnValue(permissions(['EMPLOYEE']));
    render(<HomeRouter />);
    expect(screen.getByText('Employee welcome home')).toBeInTheDocument();
  });

  it('keeps mixed-role employees on the self-service homepage', () => {
    usePermissions.mockReturnValue(permissions(['EMPLOYEE', 'CLIENT_ADMIN']));
    render(<HomeRouter />);
    expect(screen.getByText('Employee welcome home')).toBeInTheDocument();
    expect(screen.queryByText('Administrator dashboard')).not.toBeInTheDocument();
  });

  it('preserves the operational dashboard for administrators without an employee role', () => {
    usePermissions.mockReturnValue(permissions(['CLIENT_ADMIN']));
    render(<HomeRouter />);
    expect(screen.getByText('Administrator dashboard')).toBeInTheDocument();
  });
});
