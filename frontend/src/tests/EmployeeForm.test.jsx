import { render, screen } from '@testing-library/react';
import EmployeeForm from '../components/employees/EmployeeForm.jsx';

test('renders employee form', () => {
  render(<EmployeeForm onSubmit={vi.fn()} />);
  expect(screen.getByLabelText(/employee number/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/first name/i)).toBeInTheDocument();
});
