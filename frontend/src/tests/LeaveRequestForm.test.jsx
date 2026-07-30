import {
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import {
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import LeaveRequestForm from '../components/leave/LeaveRequestForm.jsx';

describe('LeaveRequestForm', () => {
  it('submits the current employee and calculated working days', () => {
    const onSubmit = vi.fn();

    render(
      <LeaveRequestForm
        employees={[{
          id: 'employee-1',
          full_name: 'Amina Otieno',
        }]}
        leaveTypes={[{
          id: 'annual-1',
          name: 'Annual leave',
          entitlement_mode: 'accrued',
        }]}
        balances={[{
          employee_id: 'employee-1',
          leave_type_id: 'annual-1',
          balance_days: 12.25,
        }]}
        defaultEmployeeId="employee-1"
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByLabelText('Employee')).toHaveValue(
      'employee-1',
    );

    fireEvent.change(
      screen.getByLabelText('Leave category'),
      { target: { value: 'annual-1' } },
    );
    fireEvent.change(
      screen.getByLabelText('Start date'),
      { target: { value: '2026-08-03' } },
    );
    fireEvent.change(
      screen.getByLabelText('End date'),
      { target: { value: '2026-08-07' } },
    );
    fireEvent.change(
      screen.getByLabelText('Reason'),
      { target: { value: 'Rest and recharge' } },
    );

    expect(
      screen.getByText('12.3 days'),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Submit request',
      }),
    );

    expect(onSubmit).toHaveBeenCalledWith({
      employee_id: 'employee-1',
      leave_type_id: 'annual-1',
      start_date: '2026-08-03',
      end_date: '2026-08-07',
      total_days: 5,
      reason: 'Rest and recharge',
    });
  });
});
