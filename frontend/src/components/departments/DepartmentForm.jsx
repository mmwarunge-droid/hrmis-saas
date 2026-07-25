import { useState } from 'react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';
import Select from '../ui/Select.jsx';

const emptyForm = {
  name: '',
  code: '',
  parent_department_id: '',
  head_employee_id: '',
};

export default function DepartmentForm({
  initialValues = {},
  departments = [],
  employees = [],
  loading = false,
  onSubmit,
  submitLabel = 'Save department',
}) {
  const [form, setForm] = useState(() => ({
    ...emptyForm,
    ...Object.fromEntries(
      Object.entries(initialValues).map(([key, value]) => [key, value ?? '']),
    ),
  }));

  const update = (event) => {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      name: form.name.trim(),
      code: form.code.trim() || null,
      parent_department_id: form.parent_department_id || null,
      head_employee_id: form.head_employee_id || null,
    });
  };

  const activeDepartments = departments.filter(
    (department) => !department.archived && department.id !== initialValues.id,
  );
  const activeEmployees = employees.filter(
    (employee) => employee.employment_status !== 'terminated',
  );

  return (
    <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
      <Input
        label="Department name"
        name="name"
        value={form.name}
        onChange={update}
        required
        maxLength={140}
      />
      <Input
        label="Department code"
        name="code"
        value={form.code}
        onChange={update}
        maxLength={40}
        placeholder="e.g. FIN"
      />
      <Select
        label="Parent department"
        name="parent_department_id"
        value={form.parent_department_id}
        onChange={update}
      >
        <option value="">No parent department</option>
        {activeDepartments.map((department) => (
          <option key={department.id} value={department.id}>{department.name}</option>
        ))}
      </Select>
      <Select
        label="Department head"
        name="head_employee_id"
        value={form.head_employee_id}
        onChange={update}
      >
        <option value="">No department head</option>
        {activeEmployees.map((employee) => (
          <option key={employee.id} value={employee.id}>
            {employee.full_name}{employee.job_title ? ` — ${employee.job_title}` : ''}
          </option>
        ))}
      </Select>
      <p className="md:col-span-2 rounded-2xl bg-cyan-50 p-4 text-sm text-cyan-900">
        Assigning a department head also moves that employee into this department and records the change in their employment history.
      </p>
      <div className="md:col-span-2">
        <Button disabled={loading}>{loading ? 'Saving...' : submitLabel}</Button>
      </div>
    </form>
  );
}
