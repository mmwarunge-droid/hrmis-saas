import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { attendanceApi } from '../api/attendanceApi.js';
import usePermissions from '../hooks/usePermissions.js';
import Attendance from '../pages/Attendance.jsx';

vi.mock('../api/attendanceApi.js', () => ({
  attendanceApi: {
    list: vi.fn(),
    summary: vi.fn(),
    today: vi.fn(),
    checkIn: vi.fn(),
    checkOut: vi.fn(),
  },
}));

vi.mock('../hooks/usePermissions.js', () => ({
  default: vi.fn(),
}));

function attendance(index) {
  return {
    id: `attendance-${index}`,
    employee_id: `employee-${index}`,
    employee_name: `Employee ${String(index).padStart(2, '0')}`,
    employee_number: `EMP-${String(index).padStart(3, '0')}`,
    work_date: `2026-07-${String((index % 28) + 1).padStart(2, '0')}`,
    check_in_at: '2026-07-01T08:00:00',
    check_out_at: index % 4 === 0 ? null : '2026-07-01T17:00:00',
    source: 'self_service',
  };
}

beforeEach(() => {
  vi.clearAllMocks();

  usePermissions.mockReturnValue({
    hasPermission: (permission) => permission === 'attendance:read',
  });

  attendanceApi.summary.mockResolvedValue({
    data: {
      total: 27,
      completed: 23,
      open_sessions: 4,
      today_checked_in: 8,
      today_completed: 6,
      today_open: 2,
    },
  });
  attendanceApi.list.mockImplementation((params) => {
    const page = params.page || 1;
    const start = ((page - 1) * 15) + 1;
    return Promise.resolve({
      data: {
        items: Array.from(
          { length: page === 2 ? 12 : 15 },
          (_, offset) => attendance(start + offset),
        ),
        meta: {
          page,
          per_page: 15,
          total: 27,
          pages: 2,
        },
      },
    });
  });
});

test('uses complete attendance summaries and server-side table controls', async () => {
  render(
    <MemoryRouter>
      <Attendance />
    </MemoryRouter>,
  );

  expect(
    await screen.findByText('Showing 15 of 27 matching attendance records'),
  ).toBeInTheDocument();
  expect(screen.getByText('1–15 of 27 attendance records'))
    .toBeInTheDocument();
  expect(screen.getByText('Completed days').closest('section'))
    .toHaveTextContent('23');
  expect(screen.getByText('Open sessions').closest('section'))
    .toHaveTextContent('4');
  expect(screen.getByText('8 checked in')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /next page/i }));

  await waitFor(() => {
    expect(attendanceApi.list).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 2,
        per_page: 15,
      }),
    );
  });

  fireEvent.change(screen.getByLabelText('Search attendance'), {
    target: { value: 'EMP-020' },
  });

  await waitFor(() => {
    expect(attendanceApi.list).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        q: 'EMP-020',
      }),
    );
    expect(attendanceApi.summary).toHaveBeenCalledWith(
      expect.objectContaining({ q: 'EMP-020' }),
    );
  });

  fireEvent.change(screen.getByLabelText('Attendance status'), {
    target: { value: 'complete' },
  });

  await waitFor(() => {
    expect(attendanceApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'complete' }),
    );
  });

  fireEvent.click(screen.getByRole('button', { name: 'Date' }));

  await waitFor(() => {
    expect(attendanceApi.list).toHaveBeenCalledWith(
      expect.objectContaining({
        sort: 'work_date',
        direction: 'asc',
      }),
    );
  });
});

test('loads and updates employee self-service attendance status', async () => {
  usePermissions.mockReturnValue({
    hasPermission: (permission) => permission === 'attendance:write',
  });
  attendanceApi.today.mockResolvedValue({ data: null });
  attendanceApi.checkIn.mockResolvedValue({
    data: {
      id: 'today-record',
      work_date: '2026-08-06',
      check_in_at: '2026-08-06T08:00:00',
      check_out_at: null,
      source: 'self_service',
    },
  });

  render(
    <MemoryRouter>
      <Attendance />
    </MemoryRouter>,
  );

  await waitFor(() => {
    expect(attendanceApi.today).toHaveBeenCalledTimes(1);
  });

  fireEvent.click(screen.getByRole('button', { name: 'Check in' }));

  await waitFor(() => {
    expect(attendanceApi.checkIn).toHaveBeenCalledTimes(1);
    expect(screen.getAllByText('In progress').length).toBeGreaterThan(0);
  });
  expect(screen.getByRole('button', { name: 'Check in' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Check out' })).toBeEnabled();
});
