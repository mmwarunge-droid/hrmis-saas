import { fireEvent, render, screen } from '@testing-library/react';
import LeaveRequestForm from '../components/leave/LeaveRequestForm.jsx';

test('event-based leave is shown as a per-event allowance', () => {
  render(
    <LeaveRequestForm
      employees={[{ id: 'employee-1', full_name: 'Employee One' }]}
      leaveTypes={[{
        id: 'maternity-1',
        name: 'Maternity leave',
        entitlement_mode: 'event_based',
        annual_entitlement_days: 90,
      }]}
      balances={[{
        employee_id: 'employee-1',
        leave_type_id: 'maternity-1',
        balance_days: 720,
      }]}
      defaultEmployeeId="employee-1"
      onSubmit={vi.fn()}
    />,
  );

  fireEvent.change(
    screen.getByLabelText('Leave category'),
    { target: { value: 'maternity-1' } },
  );

  expect(screen.getByText('Up to 90.0 days per event'))
    .toBeInTheDocument();
  expect(screen.queryByText('720.0 days')).not.toBeInTheDocument();
});

test('balance-backed leave uses backend calculated availability', () => {
  render(
    <LeaveRequestForm
      employees={[{ id: 'employee-1', full_name: 'Employee One' }]}
      leaveTypes={[{
        id: 'annual-1',
        name: 'Annual leave',
        entitlement_mode: 'accrued',
        annual_entitlement_days: 21,
      }]}
      balances={[{
        employee_id: 'employee-1',
        leave_type_id: 'annual-1',
        balance_days: 12,
        available_days: 9.5,
      }]}
      defaultEmployeeId="employee-1"
      onSubmit={vi.fn()}
    />,
  );

  fireEvent.change(
    screen.getByLabelText('Leave category'),
    { target: { value: 'annual-1' } },
  );

  expect(screen.getByText('9.5 days')).toBeInTheDocument();
});
