import { useEffect, useMemo, useState } from 'react';
import { Archive, Building2, Pencil, Plus, RefreshCcw, UsersRound } from 'lucide-react';
import { departmentApi } from '../api/departmentApi.js';
import { employeeApi } from '../api/employeeApi.js';
import DepartmentArchiveForm from '../components/departments/DepartmentArchiveForm.jsx';
import DepartmentForm from '../components/departments/DepartmentForm.jsx';
import Alert from '../components/ui/Alert.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import Modal from '../components/ui/Modal.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import usePermissions from '../hooks/usePermissions.js';

export default function Departments() {
  const [departments, setDepartments] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(null);
  const [archiveTarget, setArchiveTarget] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const { hasPermission } = usePermissions();

  const load = async () => {
    setError('');
    try {
      const [departmentResponse, employeeResponse] = await Promise.all([
        departmentApi.list({ include_archived: true }),
        employeeApi.options(),
      ]);
      setDepartments(departmentResponse.data.items || []);
      setEmployees(employeeResponse.data.items || []);
    } catch (err) {
      setError(err.error?.message || 'Unable to load departments');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      departmentApi.list({ include_archived: true }),
      employeeApi.options(),
    ])
      .then(([departmentResponse, employeeResponse]) => {
        if (cancelled) return;
        setDepartments(departmentResponse.data.items || []);
        setEmployees(employeeResponse.data.items || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.error?.message || 'Unable to load departments');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const activeDepartments = useMemo(
    () => departments.filter((department) => !department.archived),
    [departments],
  );
  const archivedDepartments = useMemo(
    () => departments.filter((department) => department.archived),
    [departments],
  );
  const unassigned = employees.filter(
    (employee) => !employee.department_id && employee.employment_status !== 'terminated',
  ).length;

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };

  const openEdit = (department) => {
    setEditing(department);
    setFormOpen(true);
  };

  const saveDepartment = async (payload) => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      if (editing) {
        await departmentApi.update(editing.id, payload);
        setMessage(`${payload.name} updated.`);
      } else {
        await departmentApi.create(payload);
        setMessage(`${payload.name} created.`);
      }
      setFormOpen(false);
      setEditing(null);
      await load();
    } catch (err) {
      setError(err.error?.message || 'Department could not be saved');
    } finally {
      setSaving(false);
    }
  };

  const archive = async (payload) => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const response = await departmentApi.archive(archiveTarget.id, payload);
      setMessage(`${archiveTarget.name} archived. ${response.data.employees_reassigned} employee(s) reassigned.`);
      setArchiveTarget(null);
      await load();
    } catch (err) {
      setError(err.error?.message || 'Department could not be archived');
    } finally {
      setSaving(false);
    }
  };

  const restore = async (department) => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await departmentApi.restore(department.id);
      setMessage(`${department.name} restored.`);
      await load();
    } catch (err) {
      setError(err.error?.message || 'Department could not be restored');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Organization design"
        title="Departments"
        description="Create teams, assign department heads and execute workforce shuffles with a complete audit trail."
        actions={hasPermission('employee:create') && (
          <Button variant="accent" onClick={openCreate}><Plus size={17} /> New department</Button>
        )}
      />

      {error && <Alert type="error">{error}</Alert>}
      {message && <Alert>{message}</Alert>}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Active departments" value={activeDepartments.length} detail="Current organizational teams" icon={Building2} tone="violet" />
        <StatCard label="Assigned people" value={employees.length - unassigned} detail="Employees mapped to a department" icon={UsersRound} tone="blue" />
        <StatCard label="Unassigned people" value={unassigned} detail="Employees requiring placement" icon={RefreshCcw} tone="amber" />
      </div>

      {loading ? (
        <div className="h-64 animate-pulse rounded-xl bg-slate-100" />
      ) : activeDepartments.length === 0 ? (
        <EmptyState
          title="No departments configured"
          description="Create the first department, assign its head and start organizing your workforce."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {activeDepartments.map((department) => (
            <Card key={department.id} className="flex h-full flex-col">
              <div className="flex items-start justify-between gap-3">
                <span className="grid h-12 w-12 place-items-center rounded-lg bg-blue-50 text-blue-700">
                  <Building2 size={21} />
                </span>
                <Badge tone="green">Active</Badge>
              </div>
              <h2 className="mt-5 text-lg font-bold text-slate-950">{department.name}</h2>
              <p className="mt-1 text-sm text-slate-500">{department.code || 'No department code'}</p>

              <div className="mt-5 grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-slate-400">People</p>
                  <p className="mt-1 font-semibold text-slate-800">{department.employee_count || 0}</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-slate-400">Parent</p>
                  <p className="mt-1 truncate font-semibold text-slate-800">{department.parent_department_name || 'Top level'}</p>
                </div>
              </div>
              <div className="mt-3 rounded-lg bg-blue-50 p-3 text-xs">
                <p className="text-blue-600">Department head</p>
                <p className="mt-1 font-semibold text-blue-900">{department.head_name || 'Not assigned'}</p>
              </div>

              {hasPermission('employee:update') && (
                <div className="mt-auto flex gap-2 pt-5">
                  <Button size="sm" variant="secondary" onClick={() => openEdit(department)}>
                    <Pencil size={14} /> Edit
                  </Button>
                  <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setArchiveTarget(department)}>
                    <Archive size={14} /> Archive
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {archivedDepartments.length > 0 && (
        <Card>
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-950">Archived departments</h2>
              <p className="text-sm text-slate-500">Historical teams remain available for audit and restoration.</p>
            </div>
            <Badge>{archivedDepartments.length}</Badge>
          </div>
          <div className="mt-5 divide-y divide-slate-100">
            {archivedDepartments.map((department) => (
              <div key={department.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <p className="font-semibold text-slate-800">{department.name}</p>
                  <p className="text-xs text-slate-500">{department.code || 'No code'} · Archived</p>
                </div>
                {hasPermission('employee:update') && (
                  <Button size="sm" variant="secondary" disabled={saving} onClick={() => restore(department)}>
                    <RefreshCcw size={14} /> Restore
                  </Button>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      <Modal
        title={editing ? `Edit ${editing.name}` : 'Create department'}
        open={formOpen}
        onClose={() => setFormOpen(false)}
      >
        <DepartmentForm
          initialValues={editing || {}}
          departments={departments}
          employees={employees}
          loading={saving}
          onSubmit={saveDepartment}
          submitLabel={editing ? 'Update department' : 'Create department'}
        />
      </Modal>

      <Modal
        title={archiveTarget ? `Archive ${archiveTarget.name}` : 'Archive department'}
        open={Boolean(archiveTarget)}
        onClose={() => setArchiveTarget(null)}
      >
        {archiveTarget && (
          <DepartmentArchiveForm
            department={archiveTarget}
            departments={departments}
            loading={saving}
            onSubmit={archive}
          />
        )}
      </Modal>
    </div>
  );
}
