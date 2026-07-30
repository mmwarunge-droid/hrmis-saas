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

import LeaveLedgerPanel from '../components/leave/LeaveLedgerPanel.jsx';

describe('LeaveLedgerPanel', () => {
  it('posts an administrator balance adjustment', async () => {
    const adjust = vi.fn().mockResolvedValue(true);

    render(
      <LeaveLedgerPanel
        entries={[{
          id: 'entry-1',
          employee_id: 'employee-1',
          leave_type_id: 'type-1',
          event_type: 'ACCRUAL',
          effective_date: '2026-08-31',
          amount_days: 1.75,
          balance_after_days: 14,
        }]}
        balances={[{
          id: 'balance-1',
          employee_id: 'employee-1',
          leave_type_id: 'type-1',
          balance_days: 14,
        }]}
        employees={[{
          id: 'employee-1',
          full_name: 'Amina Employee',
        }]}
        leaveTypes={[{
          id: 'type-1',
          name: 'Annual leave',
        }]}
        canAdjust
        onAdjust={adjust}
        onRunAccruals={vi.fn()}
      />,
    );

    fireEvent.change(
      screen.getByLabelText('Adjustment days'),
      { target: { value: '2.5' } },
    );
    fireEvent.change(
      screen.getByLabelText('Adjustment reason'),
      { target: { value: 'Approved retention benefit' } },
    );
    fireEvent.click(
      screen.getByRole('button', {
        name: 'Post adjustment',
      }),
    );

    expect(adjust).toHaveBeenCalledWith(
      'balance-1',
      {
        amount_days: 2.5,
        reason: 'Approved retention benefit',
      },
    );
    expect(
      await screen.findByText('ACCRUAL'),
    ).toBeInTheDocument();
  });
});
