import { useMemo, useState } from 'react';
import {
  History,
  Play,
  SlidersHorizontal,
} from 'lucide-react';

import Badge from '../ui/Badge.jsx';
import Button from '../ui/Button.jsx';
import Card from '../ui/Card.jsx';

function eventTone(eventType) {
  if (['ACCRUAL', 'OPENING_BALANCE', 'CARRYOVER'].includes(eventType)) {
    return 'green';
  }
  if (['EXPIRY', 'REQUEST_RESERVED'].includes(eventType)) {
    return 'amber';
  }
  if (eventType === 'MANUAL_ADJUSTMENT') {
    return 'blue';
  }
  return 'slate';
}

export default function LeaveLedgerPanel({
  entries,
  balances,
  employees,
  leaveTypes,
  canAdjust,
  onAdjust,
  onRunAccruals,
  loading,
}) {
  const [balanceId, setBalanceId] = useState('');
  const [amountDays, setAmountDays] = useState('');
  const [reason, setReason] = useState('');

  const employeeNames = useMemo(
    () => Object.fromEntries(
      employees.map((employee) => [
        employee.id,
        employee.full_name,
      ]),
    ),
    [employees],
  );
  const typeNames = useMemo(
    () => Object.fromEntries(
      leaveTypes.map((leaveType) => [
        leaveType.id,
        leaveType.name,
      ]),
    ),
    [leaveTypes],
  );

  const selectedBalanceId = balanceId || balances[0]?.id || '';

  const submitAdjustment = async (event) => {
    event.preventDefault();
    if (!selectedBalanceId || !amountDays || !reason.trim()) return;

    const completed = await onAdjust(
      selectedBalanceId,
      {
        amount_days: Number(amountDays),
        reason: reason.trim(),
      },
    );
    if (completed) {
      setAmountDays('');
      setReason('');
    }
  };

  return (
    <Card>
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="flex items-start gap-3">
          <History className="mt-1 text-violet-600" size={22} />
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-violet-700">
              Allocation ledger
            </p>
            <h2 className="mt-1 text-xl font-bold text-slate-950">
              Balance movements and scheduled allocations
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Every credit, reservation, approval, restoration,
              adjustment and expiry is recorded once.
            </p>
          </div>
        </div>

        {canAdjust && (
          <Button
            variant="secondary"
            disabled={loading}
            onClick={() => onRunAccruals({})}
          >
            <Play size={16} />
            Run allocations
          </Button>
        )}
      </div>

      {canAdjust && balances.length > 0 && (
        <form
          onSubmit={submitAdjustment}
          className="mt-5 grid gap-3 rounded-2xl bg-slate-50 p-4 lg:grid-cols-[1.4fr_140px_1.6fr_auto]"
        >
          <label className="space-y-1">
            <span className="text-xs font-semibold text-slate-600">
              Employee balance
            </span>
            <select
              aria-label="Employee balance"
              value={selectedBalanceId}
              onChange={(event) => setBalanceId(event.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2"
            >
              {balances.map((balance) => (
                <option key={balance.id} value={balance.id}>
                  {employeeNames[balance.employee_id] || 'Employee'}
                  {' — '}
                  {typeNames[balance.leave_type_id] || 'Leave'}
                  {' — '}
                  {Number(balance.balance_days || 0).toFixed(2)} days
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1">
            <span className="text-xs font-semibold text-slate-600">
              Adjustment
            </span>
            <input
              aria-label="Adjustment days"
              type="number"
              step="0.25"
              min="-365"
              max="365"
              value={amountDays}
              onChange={(event) => setAmountDays(event.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2"
              placeholder="+2.5"
              required
            />
          </label>

          <label className="space-y-1">
            <span className="text-xs font-semibold text-slate-600">
              Reason
            </span>
            <input
              aria-label="Adjustment reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2"
              placeholder="Approved correction or benefit"
              required
            />
          </label>

          <div className="flex items-end">
            <Button
              type="submit"
              disabled={
                loading
                || !selectedBalanceId
                || !amountDays
                || !reason.trim()
              }
            >
              <SlidersHorizontal size={16} />
              Post adjustment
            </Button>
          </div>
        </form>
      )}

      <div className="mt-5 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500">
              <th className="px-3 py-2">Effective</th>
              <th className="px-3 py-2">Employee</th>
              <th className="px-3 py-2">Policy</th>
              <th className="px-3 py-2">Event</th>
              <th className="px-3 py-2 text-right">Movement</th>
              <th className="px-3 py-2 text-right">Available after</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr
                key={entry.id}
                className="border-b border-slate-100"
              >
                <td className="whitespace-nowrap px-3 py-3 text-slate-600">
                  {entry.effective_date}
                </td>
                <td className="px-3 py-3 font-medium text-slate-900">
                  {entry.employee_name
                    || employeeNames[entry.employee_id]
                    || 'Employee'}
                </td>
                <td className="px-3 py-3 text-slate-600">
                  {entry.leave_type_name
                    || typeNames[entry.leave_type_id]
                    || 'Leave'}
                </td>
                <td className="px-3 py-3">
                  <Badge tone={eventTone(entry.event_type)}>
                    {entry.event_type.replaceAll('_', ' ')}
                  </Badge>
                  {entry.reason && (
                    <p className="mt-1 max-w-xs text-xs text-slate-500">
                      {entry.reason}
                    </p>
                  )}
                </td>
                <td className="px-3 py-3 text-right font-semibold text-slate-800">
                  {Number(entry.amount_days || 0) > 0 ? '+' : ''}
                  {Number(entry.amount_days || 0).toFixed(2)}
                </td>
                <td className="px-3 py-3 text-right font-semibold text-slate-800">
                  {Number(entry.balance_after_days || 0).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {entries.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-500">
            Ledger entries will appear after balances are initialized.
          </p>
        )}
      </div>
    </Card>
  );
}
