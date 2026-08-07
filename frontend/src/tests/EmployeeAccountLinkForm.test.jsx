import { fireEvent, render, screen } from '@testing-library/react';
import EmployeeAccountLinkForm from '../components/employees/EmployeeAccountLinkForm.jsx';

test('links an available user without offering already-linked accounts', () => {
  const onSubmit = vi.fn();
  render(
    <EmployeeAccountLinkForm
      employee={{ id: 'employee-1', full_name: 'Neema Hassan' }}
      users={[
        { id: 'user-1', full_name: 'Neema Hassan', email: 'neema@test', employee_profile: null },
        { id: 'user-2', full_name: 'Linked User', email: 'linked@test', employee_profile: { id: 'employee-2' } },
      ]}
      onSubmit={onSubmit}
    />,
  );

  expect(screen.queryByText(/Linked User/)).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Existing user account'), {
    target: { value: 'user-1' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Link account' }));
  expect(onSubmit).toHaveBeenCalledWith('user-1');
});
