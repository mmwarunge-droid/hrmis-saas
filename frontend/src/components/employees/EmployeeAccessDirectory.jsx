import {
  useCallback,
  useEffect,
  useState,
} from 'react';
import {
  Pencil,
  Search,
  Send,
  ShieldCheck,
  UserRoundPlus,
  X,
} from 'lucide-react';

import { employeeApi } from '../../api/employeeApi.js';
import { userApi } from '../../api/userApi.js';
import usePermissions from '../../hooks/usePermissions.js';
import EmployeeAccessForm from './EmployeeAccessForm.jsx';
import Alert from '../ui/Alert.jsx';
import Avatar from '../ui/Avatar.jsx';
import Badge from '../ui/Badge.jsx';
import Button from '../ui/Button.jsx';
import Card from '../ui/Card.jsx';
import Input from '../ui/Input.jsx';
import Modal from '../ui/Modal.jsx';
import PageHeader from '../ui/PageHeader.jsx';
import Select from '../ui/Select.jsx';
import Table from '../ui/Table.jsx';

function formatDateTime(value) {
  if (!value) return 'Never';
  return new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function AccessStatus({ access }) {
  if (!access) return <Badge tone="slate">No access</Badge>;
  if (access.status === 'invited') {
    return <Badge tone="amber">Invited</Badge>;
  }
  if (access.status === 'active') {
    return <Badge tone="green">Active</Badge>;
  }
  return <Badge tone="red">Inactive</Badge>;
}

function EmployeeAccessEditForm({ employee, loading, onSubmit }) {
  const [role, setRole] = useState(
    employee.access?.roles?.[0] || 'EMPLOYEE',
  );
  const [status, setStatus] = useState(
    employee.access?.is_active ? 'active' : 'inactive',
  );

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({
          roles: [role],
          is_active: status === 'active',
        });
      }}
    >
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <p className="font-semibold text-slate-950">{employee.full_name}</p>
        <p className="mt-1 text-sm text-slate-600">{employee.email}</p>
        <p className="mt-2 text-xs text-slate-500">
          Identity comes from the employee record. This form changes
          platform access only.
        </p>
      </div>

      <Select
        label="Access role"
        value={role}
        onChange={(event) => setRole(event.target.value)}
      >
        <option value="EMPLOYEE">Employee</option>
        <option value="MANAGER">Manager</option>
      </Select>

      <Select
        label="Platform access"
        value={status}
        onChange={(event) => setStatus(event.target.value)}
      >
        <option value="active">Active</option>
        <option value="inactive">Inactive</option>
      </Select>

      <p className="text-xs leading-5 text-slate-500">
        Deactivating platform access signs the employee out of active
        sessions. It does not change their HR employment status.
      </p>

      <div className="flex justify-end">
        <Button type="submit" variant="accent" disabled={loading}>
          {loading ? 'Saving...' : 'Save access'}
        </Button>
      </div>
    </form>
  );
}

export default function EmployeeAccessDirectory() {
  const [employees, setEmployees] = useState([]);
  const [meta, setMeta] = useState({
    page: 1,
    per_page: 15,
    total: 0,
    pages: 1,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resendingId, setResendingId] = useState(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [role, setRole] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState({
    key: 'full_name',
    direction: 'asc',
  });
  const [grantEmployee, setGrantEmployee] = useState(null);
  const [manageEmployee, setManageEmployee] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const { hasPermission } = usePermissions();

  const canGrant = (
    hasPermission('user:create')
    && hasPermission('employee:update')
  );
  const canUpdate = (
    hasPermission('user:update')
    && hasPermission('employee:update')
  );

  const loadDirectory = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await employeeApi.accessDirectory({
        page,
        per_page: 15,
        q: query || undefined,
        access_status: status || undefined,
        role: role || undefined,
        sort: sort?.key || undefined,
        direction: sort?.direction || undefined,
      });
      setEmployees(response.data.items || []);
      setMeta(response.data.meta || {
        page,
        per_page: 15,
        total: 0,
        pages: 1,
      });
    } catch (err) {
      setError(err.error?.message || 'Unable to load employee access');
    } finally {
      setLoading(false);
    }
  }, [page, query, role, sort, status]);

  useEffect(() => {
    loadDirectory();
  }, [loadDirectory]);

  const grantAccess = async (payload) => {
    if (!grantEmployee) return;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await employeeApi.provisionAccess(grantEmployee.id, payload);
      setSuccess(
        `A secure activation invitation was created for ${grantEmployee.full_name}.`,
      );
      setGrantEmployee(null);
      await loadDirectory();
    } catch (err) {
      setError(err.error?.message || 'Access could not be provisioned');
    } finally {
      setSaving(false);
    }
  };

  const updateAccess = async (payload) => {
    if (!manageEmployee) return;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const response = await employeeApi.updateAccess(
        manageEmployee.id,
        payload,
      );
      const revoked = response.data.revoked_sessions || 0;
      setSuccess(
        revoked
          ? `Access updated and ${revoked} active session${revoked === 1 ? '' : 's'} revoked.`
          : 'Access updated.',
      );
      setManageEmployee(null);
      await loadDirectory();
    } catch (err) {
      setError(err.error?.message || 'Access could not be updated');
    } finally {
      setSaving(false);
    }
  };

  const resendInvitation = async (employee) => {
    if (!employee.access?.user_id) return;
    setResendingId(employee.id);
    setError('');
    setSuccess('');
    try {
      await userApi.resendInvitation(employee.access.user_id);
      setSuccess(
        `A new activation invitation was sent to ${employee.email}.`,
      );
      await loadDirectory();
    } catch (err) {
      setError(err.error?.message || 'Invitation could not be resent');
    } finally {
      setResendingId(null);
    }
  };

  const hasFilters = Boolean(query || status || role);
  const resetFilters = () => {
    setQuery('');
    setStatus('');
    setRole('');
    setPage(1);
  };
  const updateSort = (value) => {
    setSort(value);
    setPage(1);
  };

  const columns = [
    {
      key: 'full_name',
      label: 'Employee',
      sortable: true,
      render: (employee) => (
        <div className="flex items-center gap-3">
          <Avatar name={employee.full_name} size="sm" />
          <div>
            <p className="font-semibold text-slate-900">
              {employee.full_name}
            </p>
            <p className="text-xs text-slate-500">{employee.email}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'access',
      label: 'Platform access',
      render: (employee) => <AccessStatus access={employee.access} />,
    },
    {
      key: 'role',
      label: 'Role',
      render: (employee) => (
        employee.access?.roles?.length
          ? employee.access.roles.map((item) => (
            <Badge key={item} tone="blue">
              {item.replaceAll('_', ' ')}
            </Badge>
          ))
          : <span className="text-slate-400">-</span>
      ),
    },
    {
      key: 'last_login',
      label: 'Last login',
      render: (employee) => formatDateTime(
        employee.access?.last_login_at,
      ),
    },
    {
      key: 'actions',
      label: '',
      cellClassName: 'min-w-52 text-right',
      render: (employee) => {
        if (!employee.access) {
          if (!employee.email) {
            return (
              <span className="text-xs text-amber-700">
                Work email required
              </span>
            );
          }
          if (employee.employment_status === 'terminated') {
            return (
              <span className="text-xs text-slate-400">
                Not eligible
              </span>
            );
          }
          return canGrant ? (
            <Button
              size="xs"
              variant="secondary"
              onClick={() => setGrantEmployee(employee)}
              aria-label={`Grant access to ${employee.full_name}`}
            >
              <UserRoundPlus size={14} />
              Grant access
            </Button>
          ) : null;
        }

        return canUpdate ? (
          <div className="flex flex-wrap justify-end gap-1">
            {employee.access.status === 'invited' && (
              <Button
                size="xs"
                variant="secondary"
                disabled={resendingId === employee.id}
                onClick={() => resendInvitation(employee)}
                aria-label={`Resend invitation to ${employee.full_name}`}
              >
                <Send size={14} />
                {resendingId === employee.id ? 'Sending...' : 'Resend'}
              </Button>
            )}
            <Button
              size="xs"
              variant="ghost"
              onClick={() => setManageEmployee(employee)}
              aria-label={`Manage access for ${employee.full_name}`}
            >
              <Pencil size={14} />
              Manage
            </Button>
          </div>
        ) : null;
      },
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Access & identity"
        title="People access"
        description="Grant and maintain Kinetic access for existing employees. Employee identity stays in the People directory and is never entered twice."
      />

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      <div className="rounded-xl border border-blue-200 bg-blue-50/80 px-5 py-4 text-sm text-blue-950">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 shrink-0" size={18} />
          <div>
            <p className="font-semibold">Employee-first access</p>
            <p className="mt-1 text-blue-800">
              Grant Employee or Manager access from the employee record.
              New accounts receive a private activation invitation and
              create their own password.
            </p>
          </div>
        </div>
      </div>

      <Card className="p-0">
        <div className="grid gap-3 p-4 lg:grid-cols-[minmax(0,1.8fr)_repeat(2,minmax(0,1fr))_auto]">
          <Input
            aria-label="Search employee access"
            icon={Search}
            placeholder="Search employee name, email or number"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
          <Select
            aria-label="Filter employee access by status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All access states</option>
            <option value="none">No access</option>
            <option value="invited">Invited</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </Select>
          <Select
            aria-label="Filter employee access by role"
            value={role}
            onChange={(event) => {
              setRole(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All roles</option>
            <option value="EMPLOYEE">Employee</option>
            <option value="MANAGER">Manager</option>
          </Select>
          {hasFilters && (
            <Button variant="ghost" onClick={resetFilters}>
              <X size={15} /> Clear
            </Button>
          )}
        </div>
        <div className="border-t border-slate-200 px-4 py-2.5 text-xs text-slate-500">
          Showing {employees.length} of {meta.total} matching employees
        </div>
      </Card>

      <Table
        caption="Employee platform access"
        columns={columns}
        rows={employees}
        loading={loading}
        density="compact"
        empty={
          hasFilters
            ? 'No employees match the current access filters.'
            : 'No employees found.'
        }
        sort={sort}
        onSortChange={updateSort}
        pagination={{
          page: meta.page,
          pageSize: meta.per_page,
          total: meta.total,
          onPageChange: setPage,
          label: 'employees',
        }}
      />

      <Modal
        open={Boolean(grantEmployee)}
        onClose={() => setGrantEmployee(null)}
        title="Grant platform access"
        size="lg"
      >
        {grantEmployee && (
          <EmployeeAccessForm
            employee={grantEmployee}
            loading={saving}
            onSubmit={grantAccess}
          />
        )}
      </Modal>

      <Modal
        open={Boolean(manageEmployee)}
        onClose={() => setManageEmployee(null)}
        title={
          manageEmployee
            ? `Manage access for ${manageEmployee.full_name}`
            : 'Manage access'
        }
        size="lg"
      >
        {manageEmployee && (
          <EmployeeAccessEditForm
            key={manageEmployee.id}
            employee={manageEmployee}
            loading={saving}
            onSubmit={updateAccess}
          />
        )}
      </Modal>
    </div>
  );
}
