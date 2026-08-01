import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Building2, Globe2, Plus, ShieldCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { tenantApi } from '../api/tenantApi';
import { userApi } from '../api/userApi';
import OrganizationProvisionForm from '../components/organizations/OrganizationProvisionForm.jsx';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import Modal from '../components/ui/Modal.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import useTenant from '../hooks/useTenant.js';

export default function Organizations() {
  const navigate = useNavigate();
  const {
    tenantId,
    setTenantId,
    reloadTenants,
  } = useTenant();
  const [tenants, setTenants] = useState([]);
  const [users, setUsers] = useState([]);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = async () => {
    try {
      const [tenantResponse, userResponse] = await Promise.all([tenantApi.list(), userApi.list()]);
      setTenants(tenantResponse.data.items || []);
      setUsers(userResponse.data.items || []);
    } catch (err) {
      setError(err.error?.message || 'Unable to load organizations');
    }
  };

  useEffect(() => { load(); }, []);

  const metrics = useMemo(() => {
    const active = tenants.filter((tenant) => tenant.status === 'active').length;
    const admins = users.filter((user) => user.roles?.includes('CLIENT_ADMIN')).length;
    return { active, admins, people: users.filter((user) => user.tenant_id).length };
  }, [tenants, users]);

  const provision = async (payload) => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const response = await tenantApi.provision(payload);
      setOpen(false);
      setSuccess(`${response.data.organization.name} is ready. ${response.data.admin.full_name} is the organization administrator.`);
      await Promise.all([load(), reloadTenants()]);
    } catch (err) {
      setError(err.error?.message || 'Organization provisioning failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform administration"
        title="Organizations"
        description="Provision isolated client workspaces, appoint the first organization administrator and monitor adoption across the platform."
        actions={<Button variant="accent" onClick={() => setOpen(true)}><Plus size={17} /> New organization</Button>}
      />

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Organizations" value={tenants.length} detail="Tenant workspaces on the platform" icon={Building2} tone="blue" />
        <StatCard label="Active workspaces" value={metrics.active} detail="Ready for employee operations" icon={Globe2} tone="emerald" />
        <StatCard label="Organization admins" value={metrics.admins} detail={`${metrics.people} tenant users managed`} icon={ShieldCheck} tone="violet" />
      </div>

      {tenants.length === 0 ? (
        <EmptyState
          title="No organizations yet"
          description="Create the first client workspace and its administrator in one secure flow."
          action={<Button variant="accent" onClick={() => setOpen(true)}><Plus size={16} /> Provision workspace</Button>}
        />
      ) : (
        <div className="grid gap-5 xl:grid-cols-2">
          {tenants.map((tenant) => {
            const members = users.filter((user) => user.tenant_id === tenant.id);
            const admins = members.filter((user) => user.roles?.includes('CLIENT_ADMIN'));
            return (
              <Card key={tenant.id} className="overflow-hidden">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <Avatar name={tenant.name} size="lg" className="rounded-xl" />
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-lg font-bold text-slate-950">{tenant.name}</h2>
                        <Badge tone={tenant.status === 'active' ? 'green' : 'amber'}>{tenant.status}</Badge>
                      </div>
                      <p className="mt-1 text-sm text-slate-500">{tenant.industry || 'Industry not specified'} · {tenant.country || 'Global'}</p>
                    </div>
                  </div>
                  <Badge tone="blue">{tenant.billing_plan || 'mvp'}</Badge>
                </div>
                <div className="mt-6 grid grid-cols-3 gap-3">
                  <div className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-slate-500">People</p><p className="mt-1 text-xl font-bold">{members.length}</p></div>
                  <div className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-slate-500">Admins</p><p className="mt-1 text-xl font-bold">{admins.length}</p></div>
                  <div className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-slate-500">Region</p><p className="mt-1 truncate text-sm font-bold">{tenant.compliance_region || 'Default'}</p></div>
                </div>
                <div className="mt-5 border-t border-slate-100 pt-4">
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Workspace administrator</p>
                  {admins.length ? (
                    <div className="mt-3 flex items-center gap-3">
                      <Avatar name={admins[0].full_name} size="sm" />
                      <div><p className="text-sm font-semibold text-slate-900">{admins[0].full_name}</p><p className="text-xs text-slate-500">{admins[0].email}</p></div>
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-amber-700">No CLIENT_ADMIN assigned.</p>
                  )}
                </div>
                <div className="mt-5 flex justify-end border-t border-slate-100 pt-4">
                  <Button
                    variant={
                      String(tenantId) === String(tenant.id)
                        ? 'primary'
                        : 'secondary'
                    }
                    onClick={() => {
                      setTenantId(tenant.id);
                      navigate('/dashboard');
                    }}
                  >
                    {String(tenantId) === String(tenant.id)
                      ? 'Current workspace'
                      : 'Open workspace'}
                    <ArrowRight size={16} />
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Provision organization" size="xl">
        <OrganizationProvisionForm onSubmit={provision} loading={saving} />
      </Modal>
    </div>
  );
}
