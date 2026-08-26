import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import {
  MemoryRouter,
  Route,
  Routes,
} from 'react-router-dom';

import { employeeApi } from '../api/employeeApi';
import usePermissions from '../hooks/usePermissions.js';
import EmployeeDetails from '../pages/EmployeeDetails.jsx';

vi.mock('../api/employeeApi', () => ({
  employeeApi: {
    get: vi.fn(),
    options: vi.fn(),
    departments: vi.fn(),
    history: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('../hooks/usePermissions.js', () => ({
  default: vi.fn(),
}));

vi.mock('../components/employees/EmployeeForm.jsx', () => ({
  default: ({ onSubmit, error = '', fieldErrors = {} }) => (
    <>
      {error ? <div role="alert">{error}</div> : null}

      <input
        aria-label="Mock change effective date"
        value="2026-08-27"
        readOnly
        aria-invalid={
          fieldErrors.change_effective_date ? 'true' : 'false'
        }
      />

      <button
        type="button"
        onClick={() => onSubmit({
          email: 'jane.new@acme.test',
        })}
      >
        Submit staged email change
      </button>

      <button
        type="button"
        onClick={() => onSubmit({
          job_title: 'CEO',
          change_effective_date: '2026-08-23',
          change_reason: 'Promotion',
        })}
      >
        Submit duplicate job title
      </button>

      <button
        type="button"
        onClick={() => onSubmit({
          job_title: 'People Analyst',
          change_effective_date: '2026-08-27',
          change_reason: 'Future-dated change',
        })}
      >
        Submit invalid effective date
      </button>
    </>
  ),
}));

const employee = {
  id: 'employee-1',
  tenant_id: 'tenant-1',
  user_id: 'user-1',
  employee_number: 'EMP-001',
  first_name: 'Jane',
  last_name: 'Doe',
  full_name: 'Jane Doe',
  email: 'jane.old@acme.test',
  phone: null,
  hire_date: '2026-01-01',
  termination_date: null,
  employment_status: 'active',
  employment_type: 'full_time',
  job_title: 'People Analyst',
  department_id: null,
  manager_id: null,
  work_location: 'Nairobi',
  hobbies: [],
};

beforeEach(() => {
  vi.clearAllMocks();

  usePermissions.mockReturnValue({
    hasPermission: (permission) => permission === 'employee:update',
  });

  employeeApi.get.mockResolvedValue({
    data: employee,
  });

  employeeApi.options.mockResolvedValue({
    data: { items: [] },
  });

  employeeApi.departments.mockResolvedValue({
    data: { items: [] },
  });

  employeeApi.history.mockResolvedValue({
    data: { items: [] },
  });

  employeeApi.update.mockResolvedValue({
    data: {
      ...employee,
      pending_email: 'jane.new@acme.test',
    },
    message:
      'Verification was sent to the new email address. '
      + 'The current login email remains active until '
      + 'verification is completed.',
  });
});

test('shows the staged identity-email verification message after editing an employee', async () => {
  render(
    <MemoryRouter initialEntries={['/employees/employee-1']}>
      <Routes>
        <Route
          path="/employees/:id"
          element={<EmployeeDetails />}
        />
      </Routes>
    </MemoryRouter>,
  );

  expect(
    await screen.findByRole('heading', {
      name: 'Jane Doe',
    }),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole('button', {
      name: /edit employee/i,
    }),
  );

  fireEvent.click(
    await screen.findByRole('button', {
      name: /submit staged email change/i,
    }),
  );

  await waitFor(() => {
    expect(employeeApi.update).toHaveBeenCalledWith(
      'employee-1',
      {
        email: 'jane.new@acme.test',
      },
    );
  });

  expect(
    await screen.findByText(
      /verification was sent to the new email address/i,
    ),
  ).toBeInTheDocument();

  expect(
    screen.getByText(
      /current login email remains active until verification is completed/i,
    ),
  ).toBeInTheDocument();

  expect(
    screen.queryByText('Employment details updated.'),
  ).not.toBeInTheDocument();
});


test('retries employee update with explicit duplicate-title confirmation', async () => {
  employeeApi.update
    .mockRejectedValueOnce({
      error: {
        code: 'DUPLICATE_JOB_TITLE_CONFIRMATION_REQUIRED',
        message: (
          'This organization already has an employee assigned '
          + 'to the job title CEO.'
        ),
      },
    })
    .mockResolvedValueOnce({
      data: {
        ...employee,
        job_title: 'CEO',
      },
      message: 'Employee updated',
    });

  render(
    <MemoryRouter initialEntries={['/employees/employee-1']}>
      <Routes>
        <Route
          path="/employees/:id"
          element={<EmployeeDetails />}
        />
      </Routes>
    </MemoryRouter>,
  );

  expect(
    await screen.findByRole('heading', {
      name: 'Jane Doe',
    }),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole('button', {
      name: /edit employee/i,
    }),
  );

  fireEvent.click(
    await screen.findByRole('button', {
      name: /submit duplicate job title/i,
    }),
  );

  const continueButton = await screen.findByRole('button', {
    name: /yes, continue\. this role is independent/i,
  });

  expect(screen.getAllByRole('dialog')).toHaveLength(1);

  fireEvent.click(continueButton);

  await waitFor(() => {
    expect(employeeApi.update).toHaveBeenCalledTimes(2);
  });

  expect(employeeApi.update.mock.calls[0]).toEqual([
    'employee-1',
    {
      job_title: 'CEO',
      change_effective_date: '2026-08-23',
      change_reason: 'Promotion',
    },
  ]);

  expect(employeeApi.update.mock.calls[1]).toEqual([
    'employee-1',
    {
      job_title: 'CEO',
      change_effective_date: '2026-08-23',
      change_reason: 'Promotion',
      confirm_duplicate_job_title: true,
    },
  ]);
});

test('keeps effective-date validation inside the employee edit workflow', async () => {
  employeeApi.update.mockRejectedValueOnce({
    error: {
      message: 'Effective date cannot be in the future',
    },
  });

  render(
    <MemoryRouter initialEntries={['/employees/employee-1']}>
      <Routes>
        <Route
          path="/employees/:id"
          element={<EmployeeDetails />}
        />
      </Routes>
    </MemoryRouter>,
  );

  expect(
    await screen.findByRole('heading', {
      name: 'Jane Doe',
    }),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole('button', {
      name: /edit employee/i,
    }),
  );

  fireEvent.click(
    await screen.findByRole('button', {
      name: /submit invalid effective date/i,
    }),
  );

  await waitFor(() => {
    expect(employeeApi.update).toHaveBeenCalledWith(
      'employee-1',
      {
        job_title: 'People Analyst',
        change_effective_date: '2026-08-27',
        change_reason: 'Future-dated change',
      },
    );
  });

  const dialog = screen.getByRole('dialog');
  const alert = await screen.findByRole('alert');

  expect(dialog).toContainElement(alert);
  expect(alert).toHaveTextContent(
    'Effective date cannot be in the future',
  );

  const effectiveDate = dialog.querySelector(
    '[aria-label="Mock change effective date"]',
  );

  expect(effectiveDate).not.toBeNull();
  expect(effectiveDate).toHaveAttribute('aria-invalid', 'true');
  expect(effectiveDate).toHaveValue('2026-08-27');

  // No page-level submission alert should exist behind the open workflow.
  expect(screen.getAllByRole('alert')).toHaveLength(1);
});
