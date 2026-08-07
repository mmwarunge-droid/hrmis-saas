import { useState } from 'react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';
import Select from '../ui/Select.jsx';

const today = new Date().toISOString().slice(0, 10);

const emptyForm = {
  employee_number: '',
  first_name: '',
  last_name: '',
  email: '',
  hire_date: '',
  job_title: '',
  employment_status: 'active',
  employment_type: 'full_time',
  department_id: '',
  manager_id: '',
  work_location: '',
  change_effective_date: today,
  change_reason: '',
};

function initialForm(values) {
  return Object.fromEntries(
    Object.entries(emptyForm).map(([key, fallback]) => [key, values[key] ?? fallback]),
  );
}

export default function EmployeeForm({
  onSubmit,
  loading = false,
  initialValues = {},
  employees = [],
  departments = [],
  excludeEmployeeId = null,
  submitLabel = 'Save employee',
  showChangeContext = false,
  onCancel = null,
  stickyActions = false,
}) {
  const [form, setForm] = useState(() => initialForm(initialValues));

  const update = (event) => {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  };

  const submit = (event) => {
    event.preventDefault();
    const payload = {
      employee_number: form.employee_number,
      first_name: form.first_name,
      last_name: form.last_name,
      email: form.email,
      hire_date: form.hire_date,
      job_title: form.job_title || null,
      employment_status: form.employment_status,
      employment_type: form.employment_type,
      department_id: form.department_id || null,
      manager_id: form.manager_id || null,
      work_location: form.work_location || null,
    };

    if (showChangeContext) {
      payload.change_effective_date = form.change_effective_date || null;
      payload.change_reason = form.change_reason.trim() || null;
    }
    onSubmit(payload);
  };

  const managerOptions = employees.filter(
    (employee) => employee.id !== excludeEmployeeId
      && employee.employment_status !== 'terminated',
  );
  const activeDepartments = departments.filter((department) => !department.archived);

  return (
    <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
      <Input label="Employee number" name="employee_number" value={form.employee_number} onChange={update} required />
      <Input label="Email" type="email" name="email" value={form.email} onChange={update} required />
      <Input label="First name" name="first_name" value={form.first_name} onChange={update} required />
      <Input label="Last name" name="last_name" value={form.last_name} onChange={update} required />
      <Input label="Hire date" type="date" name="hire_date" value={form.hire_date} onChange={update} required />
      <Input label="Job title" name="job_title" value={form.job_title} onChange={update} />

      <Select label="Department" name="department_id" value={form.department_id} onChange={update}>
        <option value="">No department</option>
        {activeDepartments.map((department) => (
          <option key={department.id} value={department.id}>{department.name}</option>
        ))}
      </Select>

      <Select label="Reports to" name="manager_id" value={form.manager_id} onChange={update}>
        <option value="">No manager (top level)</option>
        {managerOptions.map((employee) => (
          <option key={employee.id} value={employee.id}>
            {employee.full_name}{employee.job_title ? ` — ${employee.job_title}` : ''}
          </option>
        ))}
      </Select>

      <Select label="Employment status" name="employment_status" value={form.employment_status} onChange={update}>
        <option value="active">Active</option>
        <option value="probation">Probation</option>
        <option value="suspended">Suspended</option>
        <option value="terminated">Terminated</option>
      </Select>

      <Select label="Employment type" name="employment_type" value={form.employment_type} onChange={update}>
        <option value="full_time">Full time</option>
        <option value="part_time">Part time</option>
        <option value="contractor">Contractor</option>
        <option value="intern">Intern</option>
        <option value="temporary">Temporary</option>
      </Select>

      <Input label="Work location" name="work_location" value={form.work_location} onChange={update} />

      {showChangeContext && (
        <>
          <Input
            label="Change effective date"
            type="date"
            name="change_effective_date"
            max={today}
            value={form.change_effective_date}
            onChange={update}
          />
          <label className="block space-y-1 md:col-span-2">
            <span className="text-sm font-medium text-slate-700">Reason for employment change</span>
            <textarea
              className="min-h-24 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
              name="change_reason"
              value={form.change_reason}
              onChange={update}
              maxLength={255}
              placeholder="e.g. Promotion, team transfer or organizational restructure"
            />
          </label>
        </>
      )}

      <div
        className={`md:col-span-2 ${
          stickyActions
            ? 'sticky bottom-0 z-10 -mx-5 -mb-5 mt-2 flex items-center justify-between gap-3 border-t border-slate-200 bg-white/95 px-5 py-4 shadow-[0_-12px_24px_rgba(15,23,42,0.06)] backdrop-blur md:-mx-6 md:-mb-6 md:px-6'
            : ''
        }`}
      >
        {stickyActions && onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel} disabled={loading}>Cancel</Button>
        ) : null}
        <Button className={stickyActions ? 'ml-auto min-w-36' : ''} disabled={loading}>
          {loading ? 'Saving...' : submitLabel}
        </Button>
      </div>
    </form>
  );
}
