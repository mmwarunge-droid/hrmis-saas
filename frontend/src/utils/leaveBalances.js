export function balancesForEmployee(balances = [], employeeId) {
  if (!employeeId) return [];
  return balances.filter(
    (balance) => String(balance.employee_id) === String(employeeId),
  );
}

export function availableDays(balance) {
  return Number(
    balance?.available_days
    ?? balance?.balance_days
    ?? 0,
  );
}

export function annualLeaveMetrics(
  leaveTypes = [],
  balances = [],
  employeeId,
) {
  const annualType = leaveTypes.find(
    (type) => type.code === 'annual_leave',
  );
  const personalBalances = balancesForEmployee(balances, employeeId);
  const annualBalance = annualType
    ? personalBalances.find(
      (balance) => balance.leave_type_id === annualType.id,
    )
    : null;

  const available = availableDays(annualBalance);
  const used = Number(annualBalance?.used_days || 0);
  const reserved = Number(annualBalance?.reserved_days || 0);
  const earned = Number(
    annualBalance?.earned_days
    ?? annualBalance?.allocated_days
    ?? (available + used + reserved),
  );

  return {
    annualType,
    annualBalance,
    personalBalances,
    available,
    used,
    reserved,
    earned,
    utilization: earned > 0
      ? Math.round((used / earned) * 100)
      : 0,
  };
}

export function leaveEntitlementPresentation(type, balance) {
  const mode = type.entitlement_mode;
  const entitlement = Number(type.annual_entitlement_days || 0);

  if (mode === 'event_based') {
    return {
      value: `Up to ${entitlement.toFixed(1)} d`,
      detail: 'Per qualifying event; not a banked balance',
      balanceBacked: false,
    };
  }

  if (mode === 'unlimited') {
    return {
      value: 'Subject to approval',
      detail: 'No banked balance',
      balanceBacked: false,
    };
  }

  if (mode === 'manual') {
    return {
      value: balance
        ? `${availableDays(balance).toFixed(1)} d`
        : 'Managed by HR',
      detail: 'Manually allocated',
      balanceBacked: true,
    };
  }

  return {
    value: `${availableDays(balance).toFixed(1)} d`,
    detail: `${mode.replaceAll('_', ' ')} · ${Number(
      balance?.reserved_days || 0,
    ).toFixed(1)} reserved`,
    balanceBacked: true,
  };
}
