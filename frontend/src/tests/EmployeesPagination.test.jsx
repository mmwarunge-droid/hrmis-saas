import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { departmentApi } from '../api/departmentApi.js';
import { employeeApi } from '../api/employeeApi.js';
import usePermissions from '../hooks/usePermissions.js';
import Employees from '../pages/Employees.jsx';

vi.mock('../api/departmentApi.js', () => ({
  departmentApi: {
    list: vi.fn(),
    bulkTransfer: vi.fn(),
  },
}));

vi.mock('../api/employeeApi.js', () => ({
  employeeApi: {
    list: vi.fn(),
    summary: vi.fn(),
    options: vi.fn(),
    create: vi.fn(),
  },
}));

vi.mock('../hooks/usePermissions.js', () => ({
  default: vi.fn(),
}));

function employee(index) {
  return {
    id: `employee-${index}`,
    full_name: `Employee ${String(index).padStart(2, '0')}`,
    email: `employee-${index}@example.test`,
    job_title: 'Product Analyst',
    department_id: 'department-1',
    work_location: 'Nairobi',
    employment_status: 'active',
  };
}

beforeEach(() => {
  vi.clearAllMocks();

  usePermissions.mockReturnValue({
    hasPermission: () => false,
  });

  departmentApi.list.mockResolvedValue({
    data: {
      items: [{ id: 'department-1', name: 'Product' }],
    },
  });

  employeeApi.options.mockResolvedValue({
    data: { items: [] },
  });

  employeeApi.summary.mockResolvedValue({
    data: {
      total: 35,
      active: 27,
      not_active: 8,
      departments: 2,
      work_locations: 3,
      by_status: {
        active: 27,
        probation: 5,
        terminated: 3,
      },
    },
  });

  employeeApi.list.mockImplementation((params) => {
    const page = params.page || 1;
    const start = ((page - 1) * 15) + 1;
    const items = Array.from(
      { length: page === 3 ? 5 : 15 },
      (_, offset) => employee(start + offset),
    );

    return Promise.resolve({
      data: {
        items,
        meta: {
          page,
          per_page: 15,
          total: 35,
          pages: 3,
        },
      },
    });
  });
});

test('uses server totals, pagination, filters and sorting for the people directory', async () => {
  render(
    <MemoryRouter>
      <Employees />
    </MemoryRouter>,
  );

  expect(
    await screen.findByText('Showing 15 of 35 matching people'),
  ).toBeInTheDocument();
  expect(screen.getByText('1–15 of 35 people')).toBeInTheDocument();
  expect(screen.getByText('27 active employees')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /next page/i }));

  await waitFor(() => {
    expect(employeeApi.list).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 2,
        per_page: 15,
      }),
    );
  });

  fireEvent.change(screen.getByLabelText('Search people'), {
    target: { value: 'Nairobi' },
  });

  await waitFor(() => {
    expect(employeeApi.list).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        q: 'Nairobi',
      }),
    );
  });

  fireEvent.click(screen.getByRole('button', { name: /employee/i }));

  await waitFor(() => {
    expect(employeeApi.list).toHaveBeenCalledWith(
      expect.objectContaining({
        sort: 'full_name',
        direction: 'desc',
      }),
    );
  });
});
