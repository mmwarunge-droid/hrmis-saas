import { useMemo, useState } from 'react';
import { BriefcaseBusiness, KeyRound, UserRoundPlus } from 'lucide-react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';
import Select from '../ui/Select.jsx';

const defaultForm = {
  tenant_id: '',
  first_name: '',
  last_name: '',
  email: '',
  password: '',
  role: 'EMPLOYEE',
  employee_number: '',
  hire_date: '',
  job_title: '',
  employment_type: 'full_time',
  work_location: '',
};

export default function UserProvisionForm({ onSubmit, loading = false, isSuperAdmin = false, tenants = [] }) {
  const [form, setForm] = useState(defaultForm);
  const isEmployeeAccount = form.role !== 'CLIENT_ADMIN';
  const roleOptions = useMemo(
    () => (isSuperAdmin ? ['CLIENT_ADMIN', 'MANAGER', 'EMPLOYEE'] : ['MANAGER', 'EMPLOYEE']),
    [isSuperAdmin],
  );

  const update = (event) => setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  const submit = (event) => {
    event.preventDefault();
    const payload = {
      tenant_id: form.tenant_id || undefined,
      first_name: form.first_name,
      last_name: form.last_name,
      email: form.email,
      password: form.password,
      roles: [form.role],
    };
    if (isEmployeeAccount) {
      payload.employee_profile = {
        employee_number: form.employee_number,
        hire_date: form.hire_date,
        job_title: form.job_title || undefined,
        employment_type: form.employment_type,
        work_location: form.work_location || undefined,
      };
    }
    onSubmit(payload);
  };

  return (
    <form onSubmit={submit} className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        {isSuperAdmin && (
          <Select label="Organization" name="tenant_id" value={form.tenant_id} onChange={update} required>
            <option value="">Select organization</option>
            {tenants.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name}</option>)}
          </Select>
        )}
        <Select label="Account role" name="role" value={form.role} onChange={update}>
          {roleOptions.map((role) => <option key={role} value={role}>{role.replaceAll('_', ' ')}</option>)}
        </Select>
      </div>

      <section className="rounded-3xl border border-slate-100 bg-slate-50/70 p-5">
        <div className="mb-4 flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-cyan-100 text-cyan-800"><UserRoundPlus size={18} /></span>
          <div><h3 className="font-bold text-slate-950">User identity</h3><p className="text-xs text-slate-500">Secure sign-in and role assignment.</p></div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Input label="First name" name="first_name" value={form.first_name} onChange={update} required />
          <Input label="Last name" name="last_name" value={form.last_name} onChange={update} required />
          <Input label="Work email" type="email" name="email" value={form.email} onChange={update} required />
          <Input label="Temporary password" type="password" name="password" value={form.password} onChange={update} minLength={10} required />
        </div>
      </section>

      {isEmployeeAccount && (
        <section className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-violet-100 text-violet-800"><BriefcaseBusiness size={18} /></span>
            <div><h3 className="font-bold text-slate-950">Employee profile</h3><p className="text-xs text-slate-500">Creates the employee record in the same transaction.</p></div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Input label="Employee number" name="employee_number" value={form.employee_number} onChange={update} required />
            <Input label="Hire date" type="date" name="hire_date" value={form.hire_date} onChange={update} required />
            <Input label="Job title" name="job_title" value={form.job_title} onChange={update} />
            <Select label="Employment type" name="employment_type" value={form.employment_type} onChange={update}>
              <option value="full_time">Full time</option>
              <option value="part_time">Part time</option>
              <option value="contractor">Contractor</option>
              <option value="intern">Intern</option>
              <option value="temporary">Temporary</option>
            </Select>
            <Input label="Work location" name="work_location" value={form.work_location} onChange={update} />
          </div>
        </section>
      )}

      <div className="flex items-center justify-between gap-4">
        <p className="flex items-center gap-2 text-xs text-slate-500"><KeyRound size={15} /> The user can reset the temporary password through the secure recovery flow.</p>
        <Button variant="accent" disabled={loading}>{loading ? 'Creating...' : 'Create account'}</Button>
      </div>
    </form>
  );
}
