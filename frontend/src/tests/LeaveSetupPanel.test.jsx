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

import LeaveSetupPanel from '../components/leave/LeaveSetupPanel.jsx';

const setup = {
  missing_requirements: [],
  organization_owner: null,
  alternate_approver: null,
  governance_candidates: [
    {
      id: 'owner-1',
      full_name: 'Business Owner',
      job_title: 'Managing Director',
    },
    {
      id: 'alternate-1',
      full_name: 'Board Chair',
      job_title: 'Chairperson',
    },
  ],
  standard_pack: [{
    code: 'annual_leave',
    name: 'Annual leave',
    annual_entitlement_days: 21,
    entitlement_mode: 'accrued',
    accrual_method: 'monthly',
    pay_percentage: 100,
    eligibility_after_months: 0,
    requires_approval: true,
    carryover_allowed: true,
    max_carryover_days: 5,
    allow_negative_balance: false,
    minimum_notice_days: 7,
    documentation_after_days: null,
  }],
};

describe('LeaveSetupPanel', () => {
  it('saves governance and editable policy formulas', () => {
    const saveGovernance = vi.fn();
    const applyPack = vi.fn();

    render(
      <LeaveSetupPanel
        setup={setup}
        onSaveGovernance={saveGovernance}
        onApplyPack={applyPack}
        onInitializeBalances={vi.fn()}
      />,
    );

    fireEvent.change(
      screen.getByLabelText('Business owner'),
      { target: { value: 'owner-1' } },
    );
    fireEvent.change(
      screen.getByLabelText('Alternate approver'),
      { target: { value: 'alternate-1' } },
    );
    fireEvent.click(
      screen.getByRole('button', {
        name: 'Save approval governance',
      }),
    );

    expect(saveGovernance).toHaveBeenCalledWith({
      organization_owner_user_id: 'owner-1',
      alternate_approver_user_id: 'alternate-1',
    });

    fireEvent.change(
      screen.getByLabelText('annual_leave entitlement'),
      { target: { value: '24' } },
    );
    fireEvent.click(
      screen.getByRole('button', {
        name: 'Apply pack and initialize balances',
      }),
    );

    expect(applyPack).toHaveBeenCalledWith(
      expect.objectContaining({
        initialize_balances: true,
        policies: [
          expect.objectContaining({
            code: 'annual_leave',
            annual_entitlement_days: 24,
          }),
        ],
      }),
    );
  });
});
