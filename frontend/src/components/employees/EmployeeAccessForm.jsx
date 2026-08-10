import { useState } from 'react';
import { MailCheck, ShieldCheck } from 'lucide-react';
import Button from '../ui/Button.jsx';
import Select from '../ui/Select.jsx';

function legacySchemaNonce() {
  const values = new Uint32Array(4);
  globalThis.crypto?.getRandomValues?.(values);
  return `Invite-${Array.from(values).join('-')}-${Date.now()}!`;
}

export default function EmployeeAccessForm({
  employee,
  onSubmit,
  loading = false,
}) {
  const [role, setRole] = useState('EMPLOYEE');

  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      // Compatibility only for the existing employee-access request schema.
      // The backend invitation flow deliberately ignores this value and
      // generates an inaccessible bootstrap secret server-side.
      password: legacySchemaNonce(),
      roles: [role],
    });
  };

  return (
    <form onSubmit={submit} className="space-y-6">
      <section className="rounded-xl border border-blue-100 bg-blue-50/70 p-5">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-blue-100 text-blue-800">
            <ShieldCheck size={19} />
          </span>
          <div>
            <h3 className="font-bold text-slate-950">
              Provision access for {employee.full_name}
            </h3>
            <p className="mt-1 text-sm text-slate-600">
              The account will use {employee.email} and link directly to this
              employee record.
            </p>
          </div>
        </div>
      </section>

      <Select
        label="Access role"
        name="role"
        value={role}
        onChange={(event) => setRole(event.target.value)}
      >
        <option value="EMPLOYEE">Employee</option>
        <option value="MANAGER">Manager</option>
      </Select>

      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-blue-100 bg-blue-50/70 px-4 py-3">
        <p className="flex max-w-xl items-start gap-2 text-xs leading-5 text-blue-900">
          <MailCheck size={16} className="mt-0.5 shrink-0" />
          Kinetic will send an activation invitation to {employee.email}. The
          employee creates their own private password before sign-in.
        </p>
        <Button variant="accent" disabled={loading}>
          {loading ? 'Provisioning...' : 'Provision access'}
        </Button>
      </div>
    </form>
  );
}
