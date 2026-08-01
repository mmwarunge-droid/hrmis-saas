import { useState } from 'react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';
import Select from '../ui/Select.jsx';

const today = new Date().toISOString().slice(0, 10);

export default function DepartmentTransferModal({
  employees = [],
  departments = [],
  loading = false,
  onSubmit,
}) {
  const [departmentId, setDepartmentId] = useState('');
  const [effectiveDate, setEffectiveDate] = useState(today);
  const [reason, setReason] = useState('');

  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      employee_ids: employees.map((employee) => employee.id),
      department_id: departmentId || null,
      effective_date: effectiveDate,
      reason: reason.trim(),
    });
  };

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="rounded-lg bg-slate-50 p-4">
        <p className="text-sm font-semibold text-slate-900">
          Moving {employees.length} employee{employees.length === 1 ? '' : 's'}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          {employees.slice(0, 5).map((employee) => employee.full_name).join(', ')}
          {employees.length > 5 ? ` and ${employees.length - 5} more` : ''}
        </p>
      </div>
      <Select
        label="New department"
        value={departmentId}
        onChange={(event) => setDepartmentId(event.target.value)}
      >
        <option value="">Unassigned / no department</option>
        {departments.filter((department) => !department.archived).map((department) => (
          <option key={department.id} value={department.id}>{department.name}</option>
        ))}
      </Select>
      <Input
        label="Effective date"
        type="date"
        max={today}
        value={effectiveDate}
        onChange={(event) => setEffectiveDate(event.target.value)}
        required
      />
      <label className="block space-y-1">
        <span className="text-sm font-medium text-slate-700">Reason for change</span>
        <textarea
          className="min-h-24 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="e.g. Operating model restructure"
          maxLength={255}
          required
        />
      </label>
      <Button disabled={loading || employees.length === 0}>
        {loading ? 'Moving employees...' : `Move ${employees.length} employee${employees.length === 1 ? '' : 's'}`}
      </Button>
    </form>
  );
}
