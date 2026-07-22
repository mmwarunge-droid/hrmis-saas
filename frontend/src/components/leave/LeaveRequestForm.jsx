import { useState } from 'react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';

export default function LeaveRequestForm({ employees = [], leaveTypes = [], onSubmit, loading }) {
  const [form, setForm] = useState({ employee_id: '', leave_type_id: '', start_date: '', end_date: '', total_days: '', reason: '' });
  const update = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(form); }} className="grid gap-4 md:grid-cols-2">
      <select name="employee_id" value={form.employee_id} onChange={update} className="rounded-xl border border-slate-200 px-3 py-2" required><option value="">Select employee</option>{employees.map((e) => <option key={e.id} value={e.id}>{e.full_name}</option>)}</select>
      <select name="leave_type_id" value={form.leave_type_id} onChange={update} className="rounded-xl border border-slate-200 px-3 py-2" required><option value="">Select leave type</option>{leaveTypes.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
      <Input label="Start" name="start_date" type="date" value={form.start_date} onChange={update} required />
      <Input label="End" name="end_date" type="date" value={form.end_date} onChange={update} required />
      <Input label="Total days" name="total_days" value={form.total_days} onChange={update} required />
      <Input label="Reason" name="reason" value={form.reason} onChange={update} />
      <div className="md:col-span-2"><Button disabled={loading}>{loading ? 'Submitting...' : 'Submit request'}</Button></div>
    </form>
  );
}
