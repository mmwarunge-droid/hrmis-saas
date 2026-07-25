import { fireEvent, render, screen } from '@testing-library/react';
import EmployeeForm from '../components/employees/EmployeeForm.jsx';

test('renders employee form', () => {
  render(<EmployeeForm onSubmit={vi.fn()} />);
  expect(screen.getByLabelText(/employee number/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/first name/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/reports to/i)).toBeInTheDocument();
});

test('submits the selected manager', () => {
  const onSubmit = vi.fn();
  render(
    <EmployeeForm
      onSubmit={onSubmit}
      employees={[
        {
          id: 'manager-1',
          full_name: 'Amina Otieno',
          job_title: 'Chief People Officer',
          employment_status: 'active',
        },
      ]}
    />,
  );

  fireEvent.change(screen.getByLabelText(/employee number/i), { target: { value: 'EMP-002' } });
  fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'employee@acme.test' } });
  fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Brian' } });
  fireEvent.change(screen.getByLabelText(/last name/i), { target: { value: 'Kimani' } });
  fireEvent.change(screen.getByLabelText(/hire date/i), { target: { value: '2026-07-24' } });
  fireEvent.change(screen.getByLabelText(/reports to/i), { target: { value: 'manager-1' } });
  fireEvent.click(screen.getByRole('button', { name: /save employee/i }));

  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
    manager_id: 'manager-1',
  }));
});

test('does not submit response-only fields while editing', () => {
  const onSubmit = vi.fn();
  render(
    <EmployeeForm
      onSubmit={onSubmit}
      initialValues={{
        id: 'employee-1',
        tenant_id: 'tenant-1',
        full_name: 'Brian Kimani',
        employee_number: 'EMP-002',
        first_name: 'Brian',
        last_name: 'Kimani',
        email: 'brian@acme.test',
        hire_date: '2026-07-24',
        employment_status: 'active',
        employment_type: 'full_time',
      }}
      submitLabel="Update employee"
    />,
  );

  fireEvent.click(screen.getByRole('button', { name: /update employee/i }));

  const payload = onSubmit.mock.calls[0][0];
  expect(payload).not.toHaveProperty('id');
  expect(payload).not.toHaveProperty('tenant_id');
  expect(payload).not.toHaveProperty('full_name');
});
