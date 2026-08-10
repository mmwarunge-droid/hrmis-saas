import { useMemo, useState } from 'react';
import {
  Building2,
  MailCheck,
  ShieldCheck,
  UserCog,
} from 'lucide-react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';

const initialState = {
  organization: {
    name: '',
    slug: '',
    legal_name: '',
    country: '',
    industry: '',
    compliance_region: '',
  },
  admin: {
    first_name: '',
    last_name: '',
    email: '',
  },
};

export default function OrganizationProvisionForm({
  onSubmit,
  loading = false,
}) {
  const [form, setForm] = useState(initialState);
  const generatedSlug = useMemo(
    () => form.organization.name
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, ''),
    [form.organization.name],
  );

  const update = (section, event) => {
    const { name, value } = event.target;
    setForm((current) => ({
      ...current,
      [section]: { ...current[section], [name]: value },
    }));
  };

  const submit = (event) => {
    event.preventDefault();
    const payload = {
      ...form,
      organization: {
        ...form.organization,
        slug: form.organization.slug || generatedSlug,
      },
    };
    onSubmit(payload);
  };

  return (
    <form onSubmit={submit} className="space-y-7">
      <div className="rounded-xl bg-gradient-to-br from-slate-950 via-blue-950 to-blue-900 p-6 text-white">
        <div className="flex items-start gap-4">
          <span className="grid h-12 w-12 place-items-center rounded-lg bg-white/10">
            <Building2 size={22} />
          </span>
          <div>
            <h3 className="text-lg font-bold">
              Provision a complete organization workspace
            </h3>
            <p className="mt-1 text-sm leading-6 text-blue-100">
              The organization and its first administrator are created
              together, keeping tenant access isolated from day one.
            </p>
          </div>
        </div>
      </div>

      <section>
        <div className="mb-4 flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-blue-50 text-blue-700">
            <Building2 size={18} />
          </span>
          <div>
            <h3 className="font-bold text-slate-950">Organization profile</h3>
            <p className="text-xs text-slate-500">
              Core legal, operating and compliance context.
            </p>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Input
            label="Organization name"
            name="name"
            value={form.organization.name}
            onChange={(event) => update('organization', event)}
            required
          />
          <Input
            label="Workspace slug"
            name="slug"
            placeholder={generatedSlug || 'northstar-logistics'}
            value={form.organization.slug}
            onChange={(event) => update('organization', event)}
          />
          <Input
            label="Legal name"
            name="legal_name"
            value={form.organization.legal_name}
            onChange={(event) => update('organization', event)}
          />
          <Input
            label="Country"
            name="country"
            value={form.organization.country}
            onChange={(event) => update('organization', event)}
          />
          <Input
            label="Industry"
            name="industry"
            value={form.organization.industry}
            onChange={(event) => update('organization', event)}
          />
          <Input
            label="Compliance region"
            name="compliance_region"
            value={form.organization.compliance_region}
            onChange={(event) => update('organization', event)}
          />
        </div>
      </section>

      <section className="border-t border-slate-100 pt-6">
        <div className="mb-4 flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-blue-50 text-blue-700">
            <UserCog size={18} />
          </span>
          <div>
            <h3 className="font-bold text-slate-950">
              Organization administrator
            </h3>
            <p className="text-xs text-slate-500">
              This user receives the CLIENT_ADMIN role and can create employee
              accounts.
            </p>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Input
            label="First name"
            name="first_name"
            value={form.admin.first_name}
            onChange={(event) => update('admin', event)}
            required
          />
          <Input
            label="Last name"
            name="last_name"
            value={form.admin.last_name}
            onChange={(event) => update('admin', event)}
            required
          />
          <Input
            className="md:col-span-2"
            label="Work email"
            type="email"
            name="email"
            value={form.admin.email}
            onChange={(event) => update('admin', event)}
            required
          />
        </div>
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-blue-100 bg-blue-50/70 px-4 py-3 text-xs leading-5 text-blue-900">
          <MailCheck size={16} className="mt-0.5 shrink-0" />
          Kinetic will email the administrator a secure activation link. They
          create their own private password before first sign-in.
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
        <span className="flex items-center gap-2">
          <ShieldCheck size={18} />
          Tenant isolation and least-privilege roles are applied automatically.
        </span>
        <Button variant="accent" disabled={loading}>
          {loading ? 'Provisioning...' : 'Create workspace'}
        </Button>
      </div>
    </form>
  );
}
