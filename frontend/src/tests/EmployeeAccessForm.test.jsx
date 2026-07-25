import { fireEvent, render, screen } from '@testing-library/react';
import EmployeeAccessForm from '../components/employees/EmployeeAccessForm.jsx';

test('provisions access for the existing employee without submitting identity fields', () => {
  const onSubmit = vi.fn();
  render(
    <EmployeeAccessForm
      employee={{
        id: 'employee-1',
        full_name: 'Mark Warunge',
        email: 'sonkomuriu@gmail.com',
      }}
      onSubmit={onSubmit}
    />,
  );

  expect(screen.getByText(/sonkomuriu@gmail.com/i)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/access role/i), { target: { value: 'MANAGER' } });
  fireEvent.change(screen.getByLabelText(/temporary password/i), {
    target: { value: 'StrongTemporaryPass123!' },
  });
  fireEvent.click(screen.getByRole('button', { name: /provision access/i }));

  expect(onSubmit).toHaveBeenCalledWith({
    password: 'StrongTemporaryPass123!',
    roles: ['MANAGER'],
  });
  expect(onSubmit.mock.calls[0][0]).not.toHaveProperty('email');
  expect(onSubmit.mock.calls[0][0]).not.toHaveProperty('employee_profile');
});
