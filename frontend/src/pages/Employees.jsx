import { useEffect, useMemo, useState } from 'react';
import { ArrowRightLeft, Building2, Grid2X2, List, Network, Plus, Search, UsersRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import { departmentApi } from '../api/departmentApi.js';
import { employeeApi } from '../api/employeeApi';
import DepartmentTransferModal from '../components/departments/DepartmentTransferModal.jsx';
import EmployeeForm from '../components/employees/EmployeeForm.jsx';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import Input from '../components/ui/Input.jsx';
import Modal from '../components/ui/Modal.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import Select from '../components/ui/Select.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import Table from '../components/ui/Table.jsx';
import usePermissions from '../hooks/usePermissions';

export default function Employees() {
  const [employees, setEmployees] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [open, setOpen] = useState(false);
  const [transferOpen, setTransferOpen] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [department, setDepartment] = useState('');
  const [view, setView] = useState('cards');
  const { hasPermission } = usePermissions();

  const load = async () => {
    try {
      const [employeeResponse, departmentResponse, optionResponse] = await Promise.all([
        employeeApi.list(),
        departmentApi.list(),
        employeeApi.options(),
      ]);
      setEmployees(employeeResponse.data.items || []);
      setDepartments(departmentResponse.data.items || []);
      setEmployeeOptions(optionResponse.data.items || []);
    } catch (err) {
      setError(err.error?.message || 'Unable to load people directory');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const departmentNames = useMemo(
    () => Object.fromEntries(departments.map((item) => [item.id, item.name])),
    [departments],
  );
  const filtered = useMemo(() => employees.filter((employee) => {
    const haystack = `${employee.full_name} ${employee.email} ${employee.job_title || ''} ${employee.work_location || ''}`.toLowerCase();
    return (!query || haystack.includes(query.toLowerCase()))
      && (!status || employee.employment_status === status)
      && (!department || employee.department_id === department);
  }), [employees, query, status, department]);
  const selectedEmployees = useMemo(
    () => employees.filter((employee) => selectedIds.has(employee.id)),
    [employees, selectedIds],
  );

  const locations = new Set(employees.map((employee) => employee.work_location).filter(Boolean)).size;

  const create = async (payload) => {
    setSaving(true);
    setError('');
    try {
      await employeeApi.create(payload);
      setOpen(false);
      setMessage('Employee created.');
      await load();
    } catch (err) {
      setError(err.error?.message || 'Employee creation failed');
    } finally {
      setSaving(false);
    }
  };

  const transfer = async (payload) => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const response = await departmentApi.bulkTransfer(payload);
      setMessage(response.message || `${selectedEmployees.length} employee(s) transferred.`);
      setSelectedIds(new Set());
      setTransferOpen(false);
      await load();
    } catch (err) {
      setError(err.error?.message || 'Department transfer failed');
    } finally {
      setSaving(false);
    }
  };

  const toggleSelected = (employeeId) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });
  };

  const allVisibleSelected = filtered.length > 0 && filtered.every((employee) => selectedIds.has(employee.id));
  const toggleVisible = () => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (allVisibleSelected) filtered.forEach((employee) => next.delete(employee.id));
      else filtered.forEach((employee) => next.add(employee.id));
      return next;
    });
  };

  const columns = [
    ...(hasPermission('employee:update') ? [{
      key: 'select',
      label: '',
      render: (row) => (
        <input
          type="checkbox"
          aria-label={`Select ${row.full_name}`}
          checked={selectedIds.has(row.id)}
          onChange={() => toggleSelected(row.id)}
          className="h-4 w-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-400"
        />
      ),
    }] : []),
    {
      key: 'full_name',
      label: 'Person',
      render: (row) => (
        <Link to={`/employees/${row.id}`} className="flex items-center gap-3">
          <Avatar name={row.full_name} size="sm" />
          <div>
            <p className="font-semibold text-slate-900">{row.full_name}</p>
            <p className="text-xs text-slate-500">{row.email}</p>
          </div>
        </Link>
      ),
    },
    { key: 'job_title', label: 'Role', render: (row) => row.job_title || 'Not assigned' },
    { key: 'department_id', label: 'Department', render: (row) => departmentNames[row.department_id] || 'Unassigned' },
    { key: 'work_location', label: 'Location', render: (row) => row.work_location || '—' },
    { key: 'employment_status', label: 'Status', render: (row) => <Badge tone={row.employment_status === 'active' ? 'green' : row.employment_status === 'probation' ? 'amber' : 'slate'}>{row.employment_status}</Badge> },
  ];

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="People"
        title="People directory"
        description="A searchable employee system of record with role, team, location and reporting-line visibility."
        actions={(
          <>
            {hasPermission('employee:update') && (
              <Link to="/departments"><Button variant="secondary"><Building2 size={17} /> Manage departments</Button></Link>
            )}
            <Link to="/org-chart"><Button variant="secondary"><Network size={17} /> Org chart</Button></Link>
            {hasPermission('employee:create') && <Button variant="accent" onClick={() => setOpen(true)}><Plus size={17} /> Add employee</Button>}
          </>
        )}
      />
      {error && <Alert type="error">{error}</Alert>}
      {message && <Alert>{message}</Alert>}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Headcount" value={employees.length} detail={`${employees.filter((item) => item.employment_status === 'active').length} active employees`} icon={UsersRound} tone="blue" />
        <StatCard label="Departments" value={departments.length} detail="Organizational teams configured" icon={Building2} tone="violet" />
        <StatCard label="Work locations" value={locations} detail="Distributed workforce footprint" icon={Network} tone="emerald" />
      </div>

      <Card className="space-y-4">
        <div className="grid gap-3 lg:grid-cols-[1fr_190px_220px_auto]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-3 text-slate-400" size={18} />
            <Input aria-label="Search people" className="pl-10" placeholder="Search people, roles or locations" value={query} onChange={(event) => setQuery(event.target.value)} />
          </div>
          <Select aria-label="Employment status" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="probation">Probation</option>
            <option value="suspended">Suspended</option>
            <option value="terminated">Terminated</option>
          </Select>
          <Select aria-label="Department" value={department} onChange={(event) => setDepartment(event.target.value)}>
            <option value="">All departments</option>
            {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </Select>
          <div className="flex rounded-2xl bg-slate-100 p-1">
            <Button size="sm" variant={view === 'cards' ? 'primary' : 'ghost'} onClick={() => setView('cards')}><Grid2X2 size={16} /></Button>
            <Button size="sm" variant={view === 'list' ? 'primary' : 'ghost'} onClick={() => setView('list')}><List size={16} /></Button>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-500">Showing {filtered.length} of {employees.length} people</p>
          {hasPermission('employee:update') && filtered.length > 0 && (
            <Button size="sm" variant="ghost" onClick={toggleVisible}>
              {allVisibleSelected ? 'Clear visible selection' : 'Select visible employees'}
            </Button>
          )}
        </div>
      </Card>

      {selectedEmployees.length > 0 && (
        <Card className="flex flex-wrap items-center justify-between gap-4 border-cyan-200 bg-cyan-50/60">
          <div>
            <p className="font-semibold text-slate-950">{selectedEmployees.length} employee(s) selected</p>
            <p className="text-sm text-slate-600">Apply a department move to the entire selection in one transaction.</p>
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setSelectedIds(new Set())}>Clear</Button>
            <Button variant="accent" onClick={() => setTransferOpen(true)}><ArrowRightLeft size={17} /> Change department</Button>
          </div>
        </Card>
      )}

      {loading ? <div className="h-64 animate-pulse rounded-3xl bg-slate-100" /> : filtered.length === 0 ? (
        <EmptyState title="No people match these filters" description="Reset the filters or add a new employee record." />
      ) : view === 'list' ? (
        <Table columns={columns} rows={filtered} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((employee) => (
            <Card key={employee.id} className="relative h-full transition duration-200 hover:-translate-y-1 hover:border-cyan-200 hover:shadow-xl">
              {hasPermission('employee:update') && (
                <input
                  type="checkbox"
                  aria-label={`Select ${employee.full_name}`}
                  checked={selectedIds.has(employee.id)}
                  onChange={() => toggleSelected(employee.id)}
                  className="absolute right-5 top-5 z-10 h-4 w-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-400"
                />
              )}
              <Link to={`/employees/${employee.id}`} className="block">
                <div className="flex items-start justify-between gap-3 pr-8">
                  <Avatar name={employee.full_name} size="lg" />
                  <Badge tone={employee.employment_status === 'active' ? 'green' : 'amber'}>{employee.employment_status}</Badge>
                </div>
                <h2 className="mt-5 text-lg font-bold text-slate-950">{employee.full_name}</h2>
                <p className="mt-1 text-sm font-medium text-cyan-700">{employee.job_title || 'Role not assigned'}</p>
                <div className="mt-5 grid grid-cols-2 gap-3 text-xs">
                  <div className="rounded-2xl bg-slate-50 p-3">
                    <p className="text-slate-400">Department</p>
                    <p className="mt-1 truncate font-semibold text-slate-700">{departmentNames[employee.department_id] || 'Unassigned'}</p>
                  </div>
                  <div className="rounded-2xl bg-slate-50 p-3">
                    <p className="text-slate-400">Location</p>
                    <p className="mt-1 truncate font-semibold text-slate-700">{employee.work_location || 'Not set'}</p>
                  </div>
                </div>
                <p className="mt-4 truncate text-xs text-slate-500">{employee.email}</p>
              </Link>
            </Card>
          ))}
        </div>
      )}

      <Modal title="Create employee" open={open} onClose={() => setOpen(false)}>
        <EmployeeForm onSubmit={create} loading={saving} employees={employeeOptions} departments={departments} />
      </Modal>
      <Modal title="Change department" open={transferOpen} onClose={() => setTransferOpen(false)}>
        <DepartmentTransferModal
          employees={selectedEmployees}
          departments={departments}
          loading={saving}
          onSubmit={transfer}
        />
      </Modal>
    </div>
  );
}
