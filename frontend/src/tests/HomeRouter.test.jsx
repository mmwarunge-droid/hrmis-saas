import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import HomeRouter from '../pages/HomeRouter.jsx';
import usePermissions from '../hooks/usePermissions.js';

vi.mock('../hooks/usePermissions.js');
vi.mock('../pages/Dashboard.jsx', () => ({ default: () => <div>Administrator dashboard</div> }));
vi.mock('../pages/EmployeeHome.jsx', () => ({ default: () => <div>Employee welcome home</div> }));

describe('HomeRouter', () => {
  it('shows the welcoming homepage to employees', () => {
    usePermissions.mockReturnValue({ hasAnyRole: () => false });
    render(<HomeRouter />);
    expect(screen.getByText('Employee welcome home')).toBeInTheDocument();
  });

  it('preserves the operational dashboard for administrators', () => {
    usePermissions.mockReturnValue({ hasAnyRole: () => true });
    render(<HomeRouter />);
    expect(screen.getByText('Administrator dashboard')).toBeInTheDocument();
  });
});
