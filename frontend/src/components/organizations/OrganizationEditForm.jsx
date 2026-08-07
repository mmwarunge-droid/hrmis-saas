import { useState } from 'react';
import { Building2, ShieldAlert } from 'lucide-react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';
import Select from '../ui/Select.jsx';

export default function OrganizationEditForm({
  organization,
  loading = false,
  onSubmit,
}) {
  const [form, setForm] = useState(() => ({
    name: organization?.name || '',
    legal_name: organization?.legal_name || '',
    country: organization?.country || '',
    industry: organization?.industry || '',
    compliance_region: organization?.compliance_region || '',
    billing_plan: organization?.billing_plan || 'mvp',
    status: organization?.status || 'active',
  }));

  const update = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const submit = (event) => {
    event.preventDefault();
    onSubmit(form);
  };

  const lifecycleWarning = form.status !== 'active';

  return (
    <form className="space-y-6" onSubmit={submit}>
      <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-950">
        <div className="flex items-start gap-3">
          <Building2 className="mt-0.5 shrink-0" size={18} />
          <div>
            <p className="font-semibold">Workspace configuration</p>
            <p className="mt-1 text-blue-800">
              Slug: {organization?.slug || 'Not assigned'}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Input label="Organization name" name="name" value={form.name} onChange={update} required />
        <Input label="Legal name" name="legal_name" value={form.legal_name} onChange={update} />
        <Input label="Country" name="country" value={form.country} onChange={update} />
        <Input label="Industry" name="industry" value={form.industry} onChange={update} />
        <Input label="Compliance region" name="compliance_region" value={form.compliance_region} onChange={update} />
        <Input label="Billing plan" name="billing_plan" value={form.billing_plan} onChange={update} />
        <Select label="Workspace status" name="status" value={form.status} onChange={update}>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
          <option value="archived">Archived</option>
        </Select>
      </div>

      {lifecycleWarning && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <div className="flex items-start gap-3">
            <ShieldAlert className="mt-0.5 shrink-0" size={18} />
            <p>
              Suspending or archiving this workspace revokes its active user sessions and blocks new sign-ins until it is active again.
            </p>
          </div>
        </div>
      )}

      <div className="flex justify-end border-t border-slate-100 pt-5">
        <Button type="submit" disabled={loading}>
          {loading ? 'Saving...' : 'Save organization'}
        </Button>
      </div>
    </form>
  );
}
