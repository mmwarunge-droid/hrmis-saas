import { useEffect, useMemo, useState } from 'react';
import { KeyRound, Plus, ShieldCheck, UserCheck, UsersRound } from 'lucide-react';
import { tenantApi } from '../api/tenantApi';
import { userApi } from '../api/userApi';
import UserProvisionForm from '../components/users/UserProvisionForm.jsx';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Modal from '../components/ui/Modal.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import Table from '../components/ui/Table.jsx';
import usePermissions from '../hooks/usePermissions.js';

export default function Users() {
  const [users, setUsers] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const { hasRole, hasPermission } = usePermissions();
  const isSuperAdmin = hasRole('SUPER_ADMIN');

  const load = async () => {
    try {
      const requests = [userApi.list()];
      if (isSuperAdmin) requests.push(tenantApi.list());
      const [usersResponse, tenantsResponse] = await Promise.all(requests);
      setUsers(usersResponse.data.items || []);
      setTenants(tenantsResponse?.data.items || []);
    } catch (err) {
      setError(err.error?.message || 'Unable to load users');
    }
  };

  useEffect(() => {
    let cancelled = false;
    const requests = [userApi.list()];

    if (isSuperAdmin) {
      requests.push(tenantApi.list());
    }

    Promise.all(requests)
      .then(([usersResponse, tenantsResponse]) => {
        if (cancelled) return;

        setUsers(usersResponse.data.items || []);
        setTenants(tenantsResponse?.data.items || []);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.error?.message || 'Unable to load users');
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isSuperAdmin]);

  const tenantNames = useMemo(() => Object.fromEntries(tenants.map((tenant) => [tenant.id, tenant.name])), [tenants]);
  const stats = useMemo(() => ({
    active: users.filter((user) => user.is_active).length,
    verified: users.filter((user) => user.email_verified).length,
    admins: users.filter((user) => user.roles?.some((role) => ['SUPER_ADMIN', 'CLIENT_ADMIN'].includes(role))).length,
  }), [users]);

  const create = async (payload) => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const response = await userApi.create(payload);
      setOpen(false);
      setSuccess(`${response.data.full_name} was created${response.data.employee_profile ? ' with an employee profile' : ''}.`);
      await load();
    } catch (err) {
      setError(err.error?.message || 'User creation failed');
    } finally {
      setSaving(false);
    }
  };

  const columns = [
    {
      key: 'full_name',
      label: 'Person',
      render: (row) => (
        <div className="flex items-center gap-3">
          <Avatar name={row.full_name} size="sm" />
          <div><p className="font-semibold text-slate-900">{row.full_name}</p><p className="text-xs text-slate-500">{row.email}</p></div>
        </div>
      ),
    },
    ...(isSuperAdmin ? [{ key: 'tenant_id', label: 'Organization', render: (row) => tenantNames[row.tenant_id] || 'Platform' }] : []),
    { key: 'roles', label: 'Access', render: (row) => <div className="flex flex-wrap gap-1">{row.roles.map((role) => <Badge key={role} tone={role.includes('ADMIN') ? 'violet' : 'blue'}>{role.replaceAll('_', ' ')}</Badge>)}</div> },
    { key: 'email_verified', label: 'Verified', render: (row) => <Badge tone={row.email_verified ? 'green' : 'amber'}>{row.email_verified ? 'Verified' : 'Pending'}</Badge> },
    { key: 'is_active', label: 'Status', render: (row) => <Badge tone={row.is_active ? 'green' : 'red'}>{row.is_active ? 'Active' : 'Inactive'}</Badge> },
  ];

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Access & identity"
        title={isSuperAdmin ? 'Platform users' : 'People access'}
        description={isSuperAdmin ? 'Review users across organizations. Create organization administrators from the Organizations workspace.' : 'Create employee and manager accounts. Employee records are generated in the same secure workflow.'}
        actions={hasPermission('user:create') && <Button variant="accent" onClick={() => setOpen(true)}><Plus size={17} /> Create user</Button>}
      />

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Active users" value={stats.active} detail={`${users.length} accounts in scope`} icon={UsersRound} tone="blue" />
        <StatCard label="Verified identities" value={stats.verified} detail="Email ownership confirmed" icon={UserCheck} tone="emerald" />
        <StatCard label="Privileged users" value={stats.admins} detail="Admin access should remain limited" icon={ShieldCheck} tone="violet" />
      </div>

      <div className="rounded-3xl border border-amber-200 bg-amber-50/80 px-5 py-4 text-sm text-amber-900">
        <div className="flex items-start gap-3"><KeyRound className="mt-0.5 shrink-0" size={18} /><div><p className="font-semibold">Least-privilege administration</p><p className="mt-1 text-amber-800">Organization administrators can create managers and employees, but only platform super administrators can appoint another organization administrator.</p></div></div>
      </div>

      <Table columns={columns} rows={users} empty="No user accounts found." />

      <Modal open={open} onClose={() => setOpen(false)} title="Create user and employee profile" size="xl">
        <UserProvisionForm onSubmit={create} loading={saving} isSuperAdmin={isSuperAdmin} tenants={tenants} />
      </Modal>
    </div>
  );
}
