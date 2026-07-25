import { useState } from 'react';
import { KeyRound, ShieldCheck } from 'lucide-react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';
import Select from '../ui/Select.jsx';

export default function EmployeeAccessForm({ employee, onSubmit, loading = false }) {
  const [form, setForm] = useState({ role: 'EMPLOYEE', password: '' });
  const update = (event) => setForm((current) => ({ ...current, [event.target.name]: event.target.value }));

  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      password: form.password,
      roles: [form.role],
    });
  };

  return (
    <form onSubmit={submit} className="space-y-6">
      <section className="rounded-3xl border border-cyan-100 bg-cyan-50/70 p-5">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-cyan-100 text-cyan-800">
            <ShieldCheck size={19} />
          </span>
          <div>
            <h3 className="font-bold text-slate-950">Provision access for {employee.full_name}</h3>
            <p className="mt-1 text-sm text-slate-600">The account will use {employee.email} and link directly to this employee record.</p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <Select label="Access role" name="role" value={form.role} onChange={update}>
          <option value="EMPLOYEE">Employee</option>
          <option value="MANAGER">Manager</option>
        </Select>
        <Input
          label="Temporary password"
          type="password"
          name="password"
          value={form.password}
          onChange={update}
          minLength={10}
          autoComplete="new-password"
          required
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="flex items-center gap-2 text-xs text-slate-500">
          <KeyRound size={15} /> The employee can reset this password through the secure recovery flow.
        </p>
        <Button variant="accent" disabled={loading}>
          {loading ? 'Provisioning...' : 'Provision access'}
        </Button>
      </div>
    </form>
  );
}
