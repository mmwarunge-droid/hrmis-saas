import { fireEvent, render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';

import EmployeeAccessForm from '../components/employees/EmployeeAccessForm.jsx';

test(
  'provisions access for the existing employee without submitting identity fields',
  () => {
    const onSubmit = vi.fn();
    const employee = {
      full_name: 'Mark Warunge',
      email: 'sonkomuriu@gmail.com',
    };

    render(
      <EmployeeAccessForm
        employee={employee}
        onSubmit={onSubmit}
      />,
    );

    // The address appears in both the identity summary and invitation notice.
    expect(
      screen.getAllByText(/sonkomuriu@gmail\.com/i),
    ).toHaveLength(2);

    // Administrators no longer choose another user's password.
    expect(
      screen.queryByLabelText(/temporary password/i),
    ).not.toBeInTheDocument();

    expect(
      screen.getByText(/creates their own private password before sign-in/i),
    ).toBeInTheDocument();

    fireEvent.change(
      screen.getByLabelText(/access role/i),
      {
        target: { value: 'MANAGER' },
      },
    );

    fireEvent.click(
      screen.getByRole('button', { name: /provision access/i }),
    );

    expect(onSubmit).toHaveBeenCalledTimes(1);

    const payload = onSubmit.mock.calls[0][0];

    expect(payload).toEqual({ roles: ['MANAGER'] });

    // Existing employee identity comes from the employee record.
    expect(payload).not.toHaveProperty('email');
    expect(payload).not.toHaveProperty('first_name');
    expect(payload).not.toHaveProperty('last_name');
  },
);
