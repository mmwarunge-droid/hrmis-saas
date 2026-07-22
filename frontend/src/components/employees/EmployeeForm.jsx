import { useState } from 'react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';

export default function EmployeeForm({ onSubmit, loading = false }) {
  const [form, setForm] = useState({ employee_number: '', first_name: '', last_name: '', email: '', hire_date: '', job_title: '', employment_type: 'full_time' });
  const update = (e) => setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  const submit = (e) => { e.preventDefault(); onSubmit(form); };
  return (
    <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
      <Input label="Employee number" name="employee_number" value={form.employee_number} onChange={update} required />
      <Input label="Email" type="email" name="email" value={form.email} onChange={update} required />
      <Input label="First name" name="first_name" value={form.first_name} onChange={update} required />
      <Input label="Last name" name="last_name" value={form.last_name} onChange={update} required />
      <Input label="Hire date" type="date" name="hire_date" value={form.hire_date} onChange={update} required />
      <Input label="Job title" name="job_title" value={form.job_title} onChange={update} />
      <div className="md:col-span-2"><Button disabled={loading}>{loading ? 'Saving...' : 'Save employee'}</Button></div>
    </form>
  );
}
