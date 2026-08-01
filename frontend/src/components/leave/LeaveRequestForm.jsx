import { useMemo, useState } from 'react';

import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';

function workingDays(startValue, endValue) {
  if (!startValue || !endValue) return 0;

  const start = new Date(`${startValue}T00:00:00`);
  const end = new Date(`${endValue}T00:00:00`);
  if (end < start) return 0;

  let total = 0;
  const current = new Date(start);
  while (current <= end) {
    const day = current.getDay();
    if (day !== 0 && day !== 6) total += 1;
    current.setDate(current.getDate() + 1);
  }
  return total;
}

export default function LeaveRequestForm({
  employees = [],
  leaveTypes = [],
  balances = [],
  defaultEmployeeId = '',
  onSubmit,
  loading,
}) {
  const [form, setForm] = useState({
    employee_id: defaultEmployeeId,
    leave_type_id: '',
    start_date: '',
    end_date: '',
    reason: '',
  });

  const update = (event) => {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  };

  const totalDays = workingDays(
    form.start_date,
    form.end_date,
  );

  const selectedBalance = useMemo(
    () => balances.find(
      (balance) => (
        String(balance.employee_id) === String(form.employee_id)
        && String(balance.leave_type_id) === String(form.leave_type_id)
      ),
    ),
    [balances, form.employee_id, form.leave_type_id],
  );

  const selectedType = leaveTypes.find(
    (item) => String(item.id) === String(form.leave_type_id),
  );
  const entitlementMode = selectedType?.entitlement_mode;
  const balanceLabel = (() => {
    if (!selectedType) return 'Select a leave category';
    if (entitlementMode === 'event_based') {
      return `Up to ${Number(
        selectedType.annual_entitlement_days || 0,
      ).toFixed(1)} days per event`;
    }
    if (entitlementMode === 'unlimited') {
      return 'Subject to approval';
    }
    if (entitlementMode === 'manual' && !selectedBalance) {
      return 'Managed by HR';
    }
    return `${Number(
      selectedBalance?.available_days
      ?? selectedBalance?.balance_days
      ?? 0,
    ).toFixed(1)} days`;
  })();

  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      ...form,
      total_days: totalDays,
      reason: form.reason.trim() || null,
    });
  };

  return (
    <form
      onSubmit={submit}
      className="grid gap-4 md:grid-cols-2"
    >
      <label className="block space-y-1">
        <span className="text-sm font-medium text-slate-700">
          Employee
        </span>
        <select
          aria-label="Employee"
          name="employee_id"
          value={form.employee_id}
          onChange={update}
          className="w-full rounded-xl border border-slate-200 px-3 py-2"
          required
          disabled={employees.length === 1}
        >
          <option value="">Select employee</option>
          {employees.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.full_name}
            </option>
          ))}
        </select>
      </label>

      <label className="block space-y-1">
        <span className="text-sm font-medium text-slate-700">
          Leave category
        </span>
        <select
          aria-label="Leave category"
          name="leave_type_id"
          value={form.leave_type_id}
          onChange={update}
          className="w-full rounded-xl border border-slate-200 px-3 py-2"
          required
        >
          <option value="">Select leave type</option>
          {leaveTypes.map((type) => (
            <option key={type.id} value={type.id}>
              {type.name}
            </option>
          ))}
        </select>
      </label>

      <Input
        label="Start date"
        name="start_date"
        type="date"
        value={form.start_date}
        onChange={update}
        required
      />
      <Input
        label="End date"
        name="end_date"
        type="date"
        value={form.end_date}
        onChange={update}
        required
      />

      <div className="rounded-xl bg-slate-50 px-4 py-3">
        <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Requested weekdays
        </p>
        <p className="mt-1 text-xl font-bold text-slate-950">
          {totalDays}
        </p>
      </div>

      <div className="rounded-xl bg-blue-50 px-4 py-3">
        <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
          Available balance
        </p>
        <p className="mt-1 text-xl font-bold text-blue-950">
          {balanceLabel}
        </p>
      </div>

      <div className="md:col-span-2">
        <Input
          label="Reason"
          name="reason"
          value={form.reason}
          onChange={update}
        />
      </div>

      <div className="md:col-span-2">
        <Button
          type="submit"
          disabled={
            loading
            || !totalDays
            || !form.employee_id
            || !form.leave_type_id
          }
        >
          {loading ? 'Submitting...' : 'Submit request'}
        </Button>
      </div>
    </form>
  );
}
