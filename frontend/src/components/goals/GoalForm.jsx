import { useMemo, useState } from 'react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';
import Select from '../ui/Select.jsx';

function todayValue() {
  return new Date().toISOString().slice(0, 10);
}

function futureValue(days = 90) {
  const value = new Date();
  value.setDate(value.getDate() + days);
  return value.toISOString().slice(0, 10);
}

export default function GoalForm({
  employees = [],
  departments = [],
  onSubmit,
  loading = false,
  selfEmployee = null,
}) {
  const [form, setForm] = useState(() => ({
    title: '',
    description: '',
    owner_type: 'employee',
    employee_id: selfEmployee?.id || '',
    department_id: '',
    target_value: '100',
    current_value: '0',
    unit: '%',
    start_date: todayValue(),
    due_date: futureValue(),
    status: 'active',
  }));

  const ownerOptions = useMemo(() => (
    form.owner_type === 'employee' ? employees : departments
  ), [departments, employees, form.owner_type]);

  const update = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const submit = (event) => {
    event.preventDefault();
    const payload = {
      ...form,
      employee_id: form.owner_type === 'employee' ? form.employee_id : null,
      department_id: form.owner_type === 'department' ? form.department_id : null,
      description: form.description || null,
      target_value: Number(form.target_value),
      current_value: Number(form.current_value || 0),
    };
    onSubmit(payload);
  };

  return (
    <form className="space-y-5" onSubmit={submit}>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <Input
            label="Goal title"
            value={form.title}
            onChange={(event) => update('title', event.target.value)}
            placeholder="Increase first-week onboarding completion"
            required
          />
        </div>
        {!selfEmployee && <Select
          label="Owner type"
          value={form.owner_type}
          onChange={(event) => {
            update('owner_type', event.target.value);
            update('employee_id', '');
            update('department_id', '');
          }}
          required
        >
          <option value="employee">Employee</option>
          <option value="department">Department</option>
          <option value="organization">Organization</option>
        </Select>}
        {selfEmployee ? (
          <div className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-900">
            Personal goal for <strong>{selfEmployee.full_name}</strong>
          </div>
        ) : form.owner_type !== 'organization' ? (
          <Select
            label={form.owner_type === 'employee' ? 'Employee' : 'Department'}
            aria-label={form.owner_type === 'employee' ? 'Employee' : 'Department'}
            value={form.owner_type === 'employee' ? form.employee_id : form.department_id}
            onChange={(event) => update(
              form.owner_type === 'employee' ? 'employee_id' : 'department_id',
              event.target.value,
            )}
            required
          >
            <option value="">Select an owner</option>
            {ownerOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.full_name || item.name}
              </option>
            ))}
          </Select>
        ) : (
          <Select
            label="Goal status"
            value={form.status}
            onChange={(event) => update('status', event.target.value)}
          >
            <option value="active">Active</option>
            <option value="draft">Draft</option>
          </Select>
        )}
      </div>

      <label className="block space-y-1.5">
        <span className="text-[13px] font-semibold text-slate-700">Description</span>
        <textarea
          className="min-h-24 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition hover:border-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
          value={form.description}
          onChange={(event) => update('description', event.target.value)}
          placeholder="Describe the outcome, context, and evidence of success."
        />
      </label>

      <div className="grid gap-4 md:grid-cols-3">
        <Input
          label="Target"
          type="number"
          min="0.01"
          step="0.01"
          value={form.target_value}
          onChange={(event) => update('target_value', event.target.value)}
          required
        />
        <Input
          label="Current value"
          type="number"
          min="0"
          step="0.01"
          value={form.current_value}
          onChange={(event) => update('current_value', event.target.value)}
        />
        <Input
          label="Unit"
          value={form.unit}
          onChange={(event) => update('unit', event.target.value)}
          placeholder="%, hires, KES millions"
          required
        />
        <Input
          label="Start date"
          type="date"
          value={form.start_date}
          onChange={(event) => update('start_date', event.target.value)}
          required
        />
        <Input
          label="Due date"
          type="date"
          value={form.due_date}
          onChange={(event) => update('due_date', event.target.value)}
          required
        />
        {form.owner_type !== 'organization' && (
          <Select
            label="Goal status"
            value={form.status}
            onChange={(event) => update('status', event.target.value)}
          >
            <option value="active">Active</option>
            <option value="draft">Draft</option>
          </Select>
        )}
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={loading}>
          {loading ? 'Creating…' : 'Create goal'}
        </Button>
      </div>
    </form>
  );
}
