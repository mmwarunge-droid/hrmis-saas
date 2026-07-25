import { fireEvent, render, screen } from '@testing-library/react';
import DepartmentForm from '../components/departments/DepartmentForm.jsx';
import DepartmentTransferModal from '../components/departments/DepartmentTransferModal.jsx';

test('creates a department with parent and department head', () => {
  const onSubmit = vi.fn();
  render(
    <DepartmentForm
      onSubmit={onSubmit}
      departments={[{ id: 'parent-1', name: 'Corporate Services', archived: false }]}
      employees={[{
        id: 'employee-1',
        full_name: 'Amina Otieno',
        job_title: 'Finance Director',
        employment_status: 'active',
      }]}
    />,
  );

  fireEvent.change(screen.getByLabelText(/department name/i), { target: { value: 'Finance' } });
  fireEvent.change(screen.getByLabelText(/department code/i), { target: { value: 'FIN' } });
  fireEvent.change(screen.getByLabelText(/parent department/i), { target: { value: 'parent-1' } });
  fireEvent.change(screen.getByLabelText(/department head/i), { target: { value: 'employee-1' } });
  fireEvent.click(screen.getByRole('button', { name: /save department/i }));

  expect(onSubmit).toHaveBeenCalledWith({
    name: 'Finance',
    code: 'FIN',
    parent_department_id: 'parent-1',
    head_employee_id: 'employee-1',
  });
});

test('submits an atomic bulk department transfer payload', () => {
  const onSubmit = vi.fn();
  render(
    <DepartmentTransferModal
      onSubmit={onSubmit}
      employees={[
        { id: 'employee-1', full_name: 'Amina Otieno' },
        { id: 'employee-2', full_name: 'Brian Kimani' },
      ]}
      departments={[{ id: 'department-1', name: 'Strategy', archived: false }]}
    />,
  );

  fireEvent.change(screen.getByLabelText(/new department/i), { target: { value: 'department-1' } });
  fireEvent.change(screen.getByLabelText(/reason for change/i), { target: { value: 'Operating model restructure' } });
  fireEvent.click(screen.getByRole('button', { name: /move 2 employees/i }));

  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
    employee_ids: ['employee-1', 'employee-2'],
    department_id: 'department-1',
    reason: 'Operating model restructure',
  }));
});
