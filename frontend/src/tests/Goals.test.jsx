import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { departmentApi } from '../api/departmentApi.js';
import { employeeApi } from '../api/employeeApi.js';
import { goalApi } from '../api/goalApi.js';
import usePermissions from '../hooks/usePermissions.js';
import Goals from '../pages/Goals.jsx';

vi.mock('../api/goalApi.js', () => ({
  goalApi: {
    list: vi.fn(),
    summary: vi.fn(),
    create: vi.fn(),
    checkIn: vi.fn(),
  },
}));

vi.mock('../api/employeeApi.js', () => ({
  employeeApi: { options: vi.fn() },
}));

vi.mock('../api/departmentApi.js', () => ({
  departmentApi: { list: vi.fn() },
}));

vi.mock('../hooks/usePermissions.js', () => ({
  default: vi.fn(),
}));

const sampleGoal = {
  id: 'goal-1',
  title: 'Increase onboarding completion',
  owner_type: 'department',
  department_name: 'People',
  employee_name: null,
  current_value: 82,
  target_value: 95,
  unit: '%',
  progress_percent: 86.32,
  health: 'on_track',
  status: 'active',
  due_date: '2026-08-30',
};

beforeEach(() => {
  vi.clearAllMocks();
  usePermissions.mockReturnValue({
    hasPermission: () => true,
  });
  goalApi.summary.mockResolvedValue({
    data: {
      total: 9,
      active: 8,
      average_progress: 68.4,
      on_track: 5,
      at_risk: 2,
      off_track: 1,
      overdue: 1,
      completed: 1,
      due_soon: 2,
    },
  });
  goalApi.list.mockResolvedValue({
    data: {
      items: [sampleGoal],
      meta: { page: 1, per_page: 15, total: 21, pages: 2 },
    },
  });
  employeeApi.options.mockResolvedValue({
    data: { items: [{ id: 'employee-1', full_name: 'Neema Hassan' }] },
  });
  departmentApi.list.mockResolvedValue({
    data: { items: [{ id: 'department-1', name: 'People' }] },
  });
  goalApi.checkIn.mockResolvedValue({ data: { goal: sampleGoal } });
  goalApi.create.mockResolvedValue({ data: sampleGoal });
});

test('renders complete goal summaries and server-controlled directory data', async () => {
  render(
    <MemoryRouter>
      <Goals />
    </MemoryRouter>,
  );

  expect(await screen.findByText('Increase onboarding completion')).toBeInTheDocument();
  expect(screen.getByText('68.4%')).toBeInTheDocument();
  expect(screen.getByText('1–15 of 21 goals')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('Goal health'), {
    target: { value: 'at_risk' },
  });
  await waitFor(() => {
    expect(goalApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, health: 'at_risk' }),
    );
  });

  fireEvent.click(screen.getByRole('button', { name: /next page/i }));
  await waitFor(() => {
    expect(goalApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2 }),
    );
  });
});

test('records progress and creates an employee goal', async () => {
  render(
    <MemoryRouter>
      <Goals />
    </MemoryRouter>,
  );

  await screen.findByText('Increase onboarding completion');
  fireEvent.click(screen.getByRole('button', { name: /check in increase onboarding/i }));
  fireEvent.change(screen.getByLabelText('Current value (%)'), {
    target: { value: '90' },
  });
  fireEvent.change(screen.getByLabelText('Progress note'), {
    target: { value: 'Manager reminders completed.' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save check-in' }));

  await waitFor(() => {
    expect(goalApi.checkIn).toHaveBeenCalledWith('goal-1', {
      current_value: 90,
      health: 'on_track',
      note: 'Manager reminders completed.',
    });
  });

  fireEvent.click(screen.getByRole('button', { name: 'Create goal' }));
  fireEvent.change(screen.getByLabelText('Goal title'), {
    target: { value: 'Complete discovery certification' },
  });
  fireEvent.change(screen.getByLabelText('Employee'), {
    target: { value: 'employee-1' },
  });
  const goalForm = screen
    .getByLabelText('Employee')
    .closest('form');

  expect(goalForm).not.toBeNull();

  fireEvent.click(
    within(goalForm).getByRole('button', {
      name: 'Create goal',
    }),
  );

  await waitFor(() => {
    expect(goalApi.create).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Complete discovery certification',
        owner_type: 'employee',
        employee_id: 'employee-1',
        target_value: 100,
      }),
    );
  });
});
