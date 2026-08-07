import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { dashboardApi } from '../api/dashboardApi.js';
import { onboardingApi } from '../api/onboardingApi.js';
import useAuth from '../hooks/useAuth.js';
import usePermissions from '../hooks/usePermissions.js';
import Dashboard from '../pages/Dashboard.jsx';

vi.mock('../api/dashboardApi.js', () => ({
  dashboardApi: {
    summary: vi.fn(),
    complianceAlerts: vi.fn(),
    leaveSummary: vi.fn(),
  },
}));

vi.mock('../api/onboardingApi.js', () => ({
  onboardingApi: {
    myTasks: vi.fn(),
  },
}));

vi.mock('../hooks/useAuth.js', () => ({
  default: vi.fn(),
}));

vi.mock('../hooks/usePermissions.js', () => ({
  default: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();

  useAuth.mockReturnValue({
    user: { first_name: 'Admin' },
  });
  usePermissions.mockReturnValue({
    hasPermission: () => false,
  });

  dashboardApi.summary.mockResolvedValue({
    data: {
      employees: 35,
      active_employees: 28,
      inactive_employees: 7,
      people_health_percent: 80,
      pending_leave_requests: 27,
      recent_hires: [
        {
          id: 'employee-new',
          full_name: 'Newest Employee',
          job_title: 'People Analyst',
          hire_date: '2026-08-05',
        },
      ],
      upcoming_leave: [
        {
          id: 'leave-upcoming',
          employee_name: 'Amina Otieno',
          employee_profile_photo_url: null,
          start_date: '2026-08-10',
          end_date: '2026-08-11',
          total_days: 2,
        },
      ],
    },
  });
  dashboardApi.complianceAlerts.mockResolvedValue({
    data: {
      expiring_documents: [],
      employees_missing_contracts: [],
    },
  });
  dashboardApi.leaveSummary.mockResolvedValue({
    data: {
      by_status: {
        pending: 27,
        approved: 8,
      },
    },
  });
  onboardingApi.myTasks.mockResolvedValue({
    data: { items: [] },
  });
});

test('renders organization-wide dashboard aggregates and curated records', async () => {
  render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  );

  expect(await screen.findByText('35')).toBeInTheDocument();
  expect(screen.getByText('28 currently active')).toBeInTheDocument();
  expect(screen.getByText('80%')).toBeInTheDocument();
  expect(screen.getByText('7 not active')).toBeInTheDocument();
  expect(screen.getByText('Newest Employee')).toBeInTheDocument();
  expect(screen.getByText('Amina Otieno')).toBeInTheDocument();
});
