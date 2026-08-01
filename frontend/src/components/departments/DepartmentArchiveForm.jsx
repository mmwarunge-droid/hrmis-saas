import { useState } from 'react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';
import Select from '../ui/Select.jsx';

const today = new Date().toISOString().slice(0, 10);

export default function DepartmentArchiveForm({ department, departments, loading, onSubmit }) {
  const [replacementDepartmentId, setReplacementDepartmentId] = useState('');
  const [effectiveDate, setEffectiveDate] = useState(today);
  const [reason, setReason] = useState('Department consolidation');

  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      replacement_department_id: replacementDepartmentId || null,
      effective_date: effectiveDate,
      reason: reason.trim(),
    });
  };

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="rounded-lg bg-amber-50 p-4 text-sm text-amber-900">
        <p className="font-semibold">{department.name} has {department.employee_count || 0} active employee(s).</p>
        <p className="mt-1">Employees will be reassigned before the department is archived. Historical records are preserved.</p>
      </div>
      <Select
        label="Move employees to"
        value={replacementDepartmentId}
        onChange={(event) => setReplacementDepartmentId(event.target.value)}
      >
        <option value="">Unassigned / no department</option>
        {departments.filter((item) => !item.archived && item.id !== department.id).map((item) => (
          <option key={item.id} value={item.id}>{item.name}</option>
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
        <span className="text-sm font-medium text-slate-700">Reason</span>
        <textarea
          className="min-h-24 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={255}
          required
        />
      </label>
      <Button variant="danger" disabled={loading}>
        {loading ? 'Archiving...' : 'Archive department'}
      </Button>
    </form>
  );
}
