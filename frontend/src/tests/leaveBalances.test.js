import {
  annualLeaveMetrics,
  balancesForEmployee,
  leaveEntitlementPresentation,
} from '../utils/leaveBalances.js';

test('annual leave metrics remain scoped to the signed-in employee', () => {
  const types = [{
    id: 'annual-1',
    code: 'annual_leave',
    entitlement_mode: 'accrued',
    annual_entitlement_days: 21,
  }];
  const balances = [
    {
      employee_id: 'employee-1',
      leave_type_id: 'annual-1',
      earned_days: 12.25,
      used_days: 2,
      reserved_days: 1,
      available_days: 9.25,
    },
    {
      employee_id: 'employee-2',
      leave_type_id: 'annual-1',
      earned_days: 21,
      used_days: 0,
      reserved_days: 0,
      available_days: 21,
    },
  ];

  expect(balancesForEmployee(balances, 'employee-1'))
    .toHaveLength(1);
  expect(annualLeaveMetrics(types, balances, 'employee-1'))
    .toMatchObject({
      available: 9.25,
      used: 2,
      reserved: 1,
      earned: 12.25,
      utilization: 16,
    });
});

test('event-based entitlement is displayed as a per-event allowance', () => {
  const presentation = leaveEntitlementPresentation(
    {
      entitlement_mode: 'event_based',
      annual_entitlement_days: 90,
    },
    {
      available_days: 720,
      reserved_days: 0,
    },
  );

  expect(presentation).toEqual({
    value: 'Up to 90.0 d',
    detail: 'Per qualifying event; not a banked balance',
    balanceBacked: false,
  });
});
