import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  KeyRound,
  MailCheck,
  Send,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  UserCheck,
  UserRoundPlus,
  UsersRound,
  X,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { tenantApi } from '../api/tenantApi';
import { userApi } from '../api/userApi';
import EmployeeAccessDirectory from '../components/employees/EmployeeAccessDirectory.jsx';
import MfaPolicyPanel from '../components/security/MfaPolicyPanel.jsx';
import UserAccountEditForm from '../components/users/UserAccountEditForm.jsx';
import UserProvisionForm from '../components/users/UserProvisionForm.jsx';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Input from '../components/ui/Input.jsx';
import Modal from '../components/ui/Modal.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import Select from '../components/ui/Select.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import Table from '../components/ui/Table.jsx';
import useAuth from '../hooks/useAuth.js';
import usePermissions from '../hooks/usePermissions.js';
import useTenant from '../hooks/useTenant.js';

const ROLE_OPTIONS = [
  'SUPER_ADMIN',
  'CLIENT_ADMIN',
  'ORGANIZATION_OWNER',
  'HR_CONSULTANT',
  'MANAGER',
  'EMPLOYEE',
];

function formatDateTime(value) {
  if (!value) return 'Never';
  return new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function PlatformUsers() {
  const [users, setUsers] = useState([]);
  const [summary, setSummary] = useState({
    total: 0,
    active: 0,
    invited: 0,
    verified: 0,
    mfa_enabled: 0,
    privileged: 0,
  });
  const [meta, setMeta] = useState({
    page: 1,
    per_page: 15,
    total: 0,
    pages: 1,
  });
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [role, setRole] = useState('');
  const [organization, setOrganization] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState({
    key: 'full_name',
    direction: 'asc',
  });
  const [tenants, setTenants] = useState([]);
  const [open, setOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [saving, setSaving] = useState(false);
  const [resendingId, setResendingId] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const { user } = useAuth();
  const { tenantId } = useTenant();
  const { hasRole, hasPermission } = usePermissions();
  const isSuperAdmin = hasRole('SUPER_ADMIN');
  const canManageMfa = hasPermission('security:mfa_policy');
  const canUpdateUsers = hasPermission('user:update');
  const policyTenantId = isSuperAdmin ? tenantId : user?.tenant_id;

  const loadTenants = useCallback(async () => {
    if (!isSuperAdmin) return;
    try {
      const response = await tenantApi.options();
      setTenants(response.data.items || []);
    } catch (err) {
      setError(err.error?.message || 'Unable to load organizations');
    }
  }, [isSuperAdmin]);

  const loadSummary = useCallback(async () => {
    try {
      const response = await userApi.summary({
        tenant_id: organization || undefined,
      });
      setSummary(response.data);
    } catch (err) {
      setError(err.error?.message || 'Unable to load user totals');
    }
  }, [organization]);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await userApi.list({
        page,
        per_page: 15,
        q: query || undefined,
        status: status || undefined,
        role: role || undefined,
        tenant_id: organization || undefined,
        sort: sort?.key || undefined,
        direction: sort?.direction || undefined,
      });
      setUsers(response.data.items || []);
      setMeta(response.data.meta || {
        page,
        per_page: 15,
        total: 0,
        pages: 1,
      });
    } catch (err) {
      setError(err.error?.message || 'Unable to load users');
    } finally {
      setLoading(false);
    }
  }, [organization, page, query, role, sort, status]);

  useEffect(() => {
    loadTenants();
  }, [loadTenants]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const tenantNames = useMemo(
    () => Object.fromEntries(
      tenants.map((tenant) => [tenant.id, tenant.name]),
    ),
    [tenants],
  );

  const refresh = async () => {
    await Promise.all([loadUsers(), loadSummary(), loadTenants()]);
  };

  const create = async (payload) => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const response = await userApi.create(payload);
      setOpen(false);
      const profileText = response.data.employee_profile
        ? ' with an employee profile'
        : '';
      setSuccess(
        response.data.invitation?.delivery === 'sent'
          ? `${response.data.full_name} was created${profileText}. A secure activation invitation was sent to ${response.data.email}.`
          : `${response.data.full_name} was created${profileText}, but the activation email could not be delivered. Use Resend invitation from the user row.`,
      );
      await refresh();
    } catch (err) {
      setError(err.error?.message || 'User creation failed');
    } finally {
      setSaving(false);
    }
  };

  const resendInvitation = async (account) => {
    setResendingId(account.id);
    setError('');
    setSuccess('');
    try {
      await userApi.resendInvitation(account.id);
      setSuccess(`A new activation invitation was sent to ${account.email}.`);
      await refresh();
    } catch (err) {
      setError(err.error?.message || 'Invitation could not be resent');
    } finally {
      setResendingId(null);
    }
  };

  const saveAccount = async ({ profile, roles }) => {
    if (!selectedUser) return;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const profileResponse = await userApi.update(
        selectedUser.id,
        profile,
      );
      const previousRoles = [...(selectedUser.roles || [])].sort();
      const updatedRoles = [...roles].sort();
      if (previousRoles.join('|') !== updatedRoles.join('|')) {
        await userApi.updateRoles(selectedUser.id, roles);
      }
      setSelectedUser(null);
      const revoked = profileResponse.data.revoked_sessions || 0;
      setSuccess(
        revoked
          ? `Account updated and ${revoked} active session${revoked === 1 ? '' : 's'} revoked.`
          : 'Account updated.',
      );
      await refresh();
    } catch (err) {
      setError(err.error?.message || 'User update failed');
    } finally {
      setSaving(false);
    }
  };

  const resetFilters = () => {
    setQuery('');
    setStatus('');
    setRole('');
    setOrganization('');
    setPage(1);
  };

  const hasFilters = Boolean(query || status || role || organization);
  const canManageAccount = (account) => (
    isSuperAdmin
    || (
      String(account.id) !== String(user?.id)
      && (account.roles || []).every(
        (item) => ['MANAGER', 'EMPLOYEE'].includes(item),
      )
    )
  );
  const updateSort = (value) => {
    setSort(value);
    setPage(1);
  };

  const columns = [
    {
      key: 'full_name',
      label: 'Person',
      sortable: true,
      render: (row) => (
        <div className="flex items-center gap-3">
          <Avatar name={row.full_name} size="sm" />
          <div>
            <p className="font-semibold text-slate-900">{row.full_name}</p>
            <p className="text-xs text-slate-500">{row.email}</p>
          </div>
        </div>
      ),
    },
    ...(isSuperAdmin ? [{
      key: 'organization',
      label: 'Organization',
      sortable: true,
      render: (row) => tenantNames[row.tenant_id] || 'Platform',
    }] : []),
    {
      key: 'roles',
      label: 'Access',
      render: (row) => (
        <div className="flex flex-wrap gap-1">
          {(row.roles || []).map((item) => (
            <Badge
              key={item}
              tone={item.includes('ADMIN') ? 'violet' : 'blue'}
            >
              {item.replaceAll('_', ' ')}
            </Badge>
          ))}
        </div>
      ),
    },
    {
      key: 'verified',
      label: 'Verified',
      sortable: true,
      render: (row) => (
        <Badge tone={row.email_verified ? 'green' : 'amber'}>
          {row.email_verified ? 'Verified' : 'Pending'}
        </Badge>
      ),
    },
    {
      key: 'mfa',
      label: 'MFA',
      sortable: true,
      render: (row) => (
        <Badge tone={row.mfa_enabled ? 'green' : 'slate'}>
          {row.mfa_enabled ? 'Enabled' : 'Not enabled'}
        </Badge>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      sortable: true,
      render: (row) => {
        const accountStatus = row.account_status
          || (row.is_active ? 'active' : 'suspended');
        const tone = accountStatus === 'active'
          ? 'green'
          : accountStatus === 'invited'
            ? 'amber'
            : 'red';
        const label = accountStatus === 'invited'
          ? 'Invited'
          : accountStatus === 'active'
            ? 'Active'
            : 'Inactive';
        return <Badge tone={tone}>{label}</Badge>;
      },
    },
    {
      key: 'last_login',
      label: 'Last login',
      sortable: true,
      render: (row) => formatDateTime(row.last_login_at),
    },
    ...(canUpdateUsers ? [{
      key: 'actions',
      label: '',
      cellClassName: 'min-w-44 text-right',
      render: (row) => (
        canManageAccount(row) ? (
          <div className="flex flex-wrap justify-end gap-1">
            {row.account_status === 'invited' && (
              <Button
                size="xs"
                variant="secondary"
                disabled={resendingId === row.id}
                onClick={() => resendInvitation(row)}
                aria-label={`Resend invitation to ${row.full_name}`}
              >
                <Send size={14} />
                {resendingId === row.id ? 'Sending...' : 'Resend'}
              </Button>
            )}
            <Button
              size="xs"
              variant="ghost"
              onClick={() => setSelectedUser(row)}
              aria-label={`Manage ${row.full_name}`}
            >
              <Pencil size={14} />
              Manage
            </Button>
          </div>
        ) : (
          <span className="text-xs text-slate-400">Protected</span>
        )
      ),
    }] : []),
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Access & identity"
        title={isSuperAdmin ? 'Platform users' : 'People access'}
        description={isSuperAdmin
          ? 'Review identities across organizations, send secure first-time activation invitations and keep privileged access deliberately limited.'
          : 'Create employee and manager accounts through private activation invitations, maintain access roles and immediately deactivate accounts when access should end.'}
        actions={hasPermission('user:create') && (
          <Button variant="accent" onClick={() => setOpen(true)}>
            <Plus size={17} /> Create user
          </Button>
        )}
      />

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="User accounts" value={summary.total} detail="Complete identity scope" icon={UsersRound} tone="blue" />
        <StatCard label="Active users" value={summary.active} detail={`${summary.invited || 0} awaiting activation`} icon={UserCheck} tone="emerald" />
        <StatCard label="Verified identities" value={summary.verified} detail={`${summary.mfa_enabled} with MFA enabled`} icon={KeyRound} tone="blue" />
        <StatCard label="Privileged users" value={summary.privileged} detail="Review administrative access regularly" icon={ShieldCheck} tone="violet" />
      </div>

      {canManageMfa && policyTenantId && (
        <MfaPolicyPanel
          tenantId={policyTenantId}
          currentUserId={user?.id}
        />
      )}

      <div className="rounded-xl border border-blue-200 bg-blue-50/80 px-5 py-4 text-sm text-blue-950">
        <div className="flex items-start gap-3">
          <MailCheck className="mt-0.5 shrink-0" size={18} />
          <div>
            <p className="font-semibold">Private first-time activation</p>
            <p className="mt-1 text-blue-800">
              New users receive a single-use email invitation and create their own password. Administrators never know or distribute another user’s credential.
            </p>
          </div>
        </div>
      </div>

      {!isSuperAdmin && (
        <div className="rounded-xl border border-blue-200 bg-blue-50/80 px-5 py-4 text-sm text-blue-950">
          <div className="flex items-start gap-3">
            <UserRoundPlus className="mt-0.5 shrink-0" size={18} />
            <div>
              <p className="font-semibold">Employee already exists?</p>
              <p className="mt-1 text-blue-800">
                Open the employee in the <Link className="font-semibold underline" to="/employees">People directory</Link> and choose Provision access. This links the account without creating a duplicate employee record.
              </p>
            </div>
          </div>
        </div>
      )}

      <Card className="p-0">
        <div className="grid gap-3 p-4 lg:grid-cols-[minmax(0,1.8fr)_repeat(3,minmax(0,1fr))_auto]">
          <Input
            aria-label="Search user accounts"
            icon={Search}
            placeholder="Search people, email, role or organization"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
          <Select
            aria-label="Filter users by status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="invited">Invited</option>
            <option value="inactive">Inactive</option>
          </Select>
          <Select
            aria-label="Filter users by role"
            value={role}
            onChange={(event) => {
              setRole(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All roles</option>
            {ROLE_OPTIONS
              .filter((item) => isSuperAdmin || ['MANAGER', 'EMPLOYEE'].includes(item))
              .map((item) => (
                <option key={item} value={item}>
                  {item.replaceAll('_', ' ')}
                </option>
              ))}
          </Select>
          {isSuperAdmin ? (
            <Select
              aria-label="Filter users by organization"
              value={organization}
              onChange={(event) => {
                setOrganization(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All organizations</option>
              {tenants.map((tenant) => (
                <option key={tenant.id} value={tenant.id}>
                  {tenant.name}
                </option>
              ))}
            </Select>
          ) : <span />}
          {hasFilters && (
            <Button variant="ghost" onClick={resetFilters}>
              <X size={15} /> Clear
            </Button>
          )}
        </div>
        <div className="border-t border-slate-200 px-4 py-2.5 text-xs text-slate-500">
          Showing {users.length} of {meta.total} matching accounts
        </div>
      </Card>

      <Table
        caption="User accounts"
        columns={columns}
        rows={users}
        loading={loading}
        density="compact"
        empty={hasFilters ? 'No users match the current filters.' : 'No user accounts found.'}
        sort={sort}
        onSortChange={updateSort}
        pagination={{
          page: meta.page,
          pageSize: meta.per_page,
          total: meta.total,
          onPageChange: setPage,
          label: 'user accounts',
        }}
      />

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Create new user and employee profile"
        size="xl"
      >
        <UserProvisionForm
          onSubmit={create}
          loading={saving}
          isSuperAdmin={isSuperAdmin}
          tenants={tenants}
        />
      </Modal>

      <Modal
        open={Boolean(selectedUser)}
        onClose={() => setSelectedUser(null)}
        title="Manage user account"
        description="Update identity details, lifecycle status and assigned access roles."
        size="lg"
      >
        {selectedUser && (
          <UserAccountEditForm
            key={selectedUser.id}
            account={selectedUser}
            currentUserId={user?.id}
            isSuperAdmin={isSuperAdmin}
            loading={saving}
            onSubmit={saveAccount}
          />
        )}
      </Modal>
    </div>
  );
}

export default function Users() {
  const { hasRole } = usePermissions();
  return hasRole('SUPER_ADMIN')
    ? <PlatformUsers />
    : <EmployeeAccessDirectory />;
}
