import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRightLeft,
  Building2,
  Grid2X2,
  List,
  Network,
  Plus,
  Search,
  SlidersHorizontal,
  UsersRound,
  X,
} from 'lucide-react';
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
  const [view, setView] = useState('list');
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

  useEffect(() => { load(); }, []);

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
  const activeCount = employees.filter((item) => item.employment_status === 'active').length;
  const hasFilters = Boolean(query || status || department);

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

  const resetFilters = () => {
    setQuery('');
    setStatus('');
    setDepartment('');
  };

  const columns = [
    ...(hasPermission('employee:update') ? [{
      key: 'select',
      label: '',
      cellClassName: 'w-10',
      render: (row) => (
        <input
          type="checkbox"
          aria-label={`Select ${row.full_name}`}
          checked={selectedIds.has(row.id)}
          onChange={() => toggleSelected(row.id)}
          className="h-4 w-4 rounded border-slate-300 text-blue-700 focus:ring-blue-400"
        />
      ),
    }] : []),
    {
      key: 'full_name',
      label: 'Employee',
      sortable: true,
      render: (row) => (
        <Link to={`/employees/${row.id}`} className="flex min-w-56 items-center gap-3 group/person">
          <Avatar name={row.full_name} size="sm" src={row.profile_photo_url} />
          <div className="min-w-0">
            <p className="truncate font-semibold text-slate-900 group-hover/person:text-blue-700">{row.full_name}</p>
            <p className="truncate text-xs text-slate-500">{row.email}</p>
          </div>
        </Link>
      ),
    },
    { key: 'job_title', label: 'Job title', sortable: true, render: (row) => row.job_title || 'Not assigned' },
    { key: 'department_id', label: 'Department', sortable: true, sortValue: (row) => departmentNames[row.department_id] || '', render: (row) => departmentNames[row.department_id] || 'Unassigned' },
    { key: 'work_location', label: 'Location', sortable: true, render: (row) => row.work_location || '—' },
    {
      key: 'employment_status',
      label: 'Status',
      sortable: true,
      render: (row) => (
        <Badge tone={row.employment_status === 'active' ? 'green' : row.employment_status === 'probation' ? 'amber' : 'slate'}>
          {row.employment_status}
        </Badge>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="People"
        title="People directory"
        description="Find employee records, reporting relationships, teams, and work details."
        actions={(
          <>
            <Link to="/org-chart"><Button variant="secondary"><Network size={16} /> Org chart</Button></Link>
            {hasPermission('employee:create') && <Button onClick={() => setOpen(true)}><Plus size={16} /> Add employee</Button>}
          </>
        )}
      />

      {error && <Alert type="error">{error}</Alert>}
      {message && <Alert type="success">{message}</Alert>}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Headcount" value={employees.length} detail={`${activeCount} active employees`} icon={UsersRound} tone="blue" />
        <StatCard label="Departments" value={departments.length} detail="Organizational teams" icon={Building2} tone="violet" />
        <StatCard label="Work locations" value={locations} detail="Workforce footprint" icon={Network} tone="emerald" />
      </div>

      <Card padded={false}>
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 lg:flex-row lg:items-center">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-3 text-slate-400" size={17} />
            <Input aria-label="Search people" className="pl-9" placeholder="Search people, job titles, or locations" value={query} onChange={(event) => setQuery(event.target.value)} />
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:flex">
            <Select aria-label="Employment status" className="lg:w-44" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="probation">Probation</option>
              <option value="suspended">Suspended</option>
              <option value="terminated">Terminated</option>
            </Select>
            <Select aria-label="Department" className="lg:w-52" value={department} onChange={(event) => setDepartment(event.target.value)}>
              <option value="">All departments</option>
              {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </Select>
          </div>
          {hasFilters && <Button size="sm" variant="ghost" onClick={resetFilters}><X size={15} /> Clear</Button>}
          <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
            <Button size="sm" variant={view === 'list' ? 'secondary' : 'ghost'} className="min-h-8 px-2" onClick={() => setView('list')} aria-label="List view"><List size={16} /></Button>
            <Button size="sm" variant={view === 'cards' ? 'secondary' : 'ghost'} className="min-h-8 px-2" onClick={() => setView('cards')} aria-label="Card view"><Grid2X2 size={16} /></Button>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1.5"><SlidersHorizontal size={14} /> Showing {filtered.length} of {employees.length} people</span>
          {hasPermission('employee:update') && filtered.length > 0 && (
            <button type="button" className="font-semibold text-blue-700 hover:text-blue-900" onClick={toggleVisible}>
              {allVisibleSelected ? 'Clear visible selection' : 'Select visible employees'}
            </button>
          )}
        </div>
      </Card>

      {selectedEmployees.length > 0 && (
        <div className="sticky top-20 z-20 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 shadow-lg shadow-blue-950/5">
          <div>
            <p className="text-sm font-bold text-slate-950">{selectedEmployees.length} selected</p>
            <p className="text-xs text-slate-600">Apply one department move to the selected employee records.</p>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>Clear</Button>
            <Button size="sm" onClick={() => setTransferOpen(true)}><ArrowRightLeft size={15} /> Change department</Button>
          </div>
        </div>
      )}

      {view === 'list' ? (
        <Table columns={columns} rows={filtered} loading={loading} pageSize={15} empty={hasFilters ? 'No people match these filters.' : 'No employee records yet.'} caption="People directory" />
      ) : loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, index) => <div key={index} className="h-52 animate-pulse rounded-xl bg-slate-200" />)}</div>
      ) : filtered.length === 0 ? (
        <EmptyState title="No people match these filters" description="Clear the filters or add a new employee record." icon={UsersRound} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((employee) => (
            <Card key={employee.id} className="relative transition hover:border-blue-200 hover:shadow-md">
              {hasPermission('employee:update') && (
                <input
                  type="checkbox"
                  aria-label={`Select ${employee.full_name}`}
                  checked={selectedIds.has(employee.id)}
                  onChange={() => toggleSelected(employee.id)}
                  className="absolute right-4 top-4 z-10 h-4 w-4 rounded border-slate-300 text-blue-700 focus:ring-blue-400"
                />
              )}
              <Link to={`/employees/${employee.id}`} className="block">
                <div className="flex items-center gap-3 pr-7">
                  <Avatar name={employee.full_name} size="lg" src={employee.profile_photo_url} />
                  <div className="min-w-0 flex-1">
                    <h2 className="truncate text-base font-bold text-slate-950">{employee.full_name}</h2>
                    <p className="mt-0.5 truncate text-sm text-slate-600">{employee.job_title || 'Role not assigned'}</p>
                    <Badge className="mt-2" tone={employee.employment_status === 'active' ? 'green' : 'amber'}>{employee.employment_status}</Badge>
                  </div>
                </div>
                <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-slate-100 pt-4 text-xs">
                  <div><dt className="text-slate-400">Department</dt><dd className="mt-1 truncate font-semibold text-slate-700">{departmentNames[employee.department_id] || 'Unassigned'}</dd></div>
                  <div><dt className="text-slate-400">Location</dt><dd className="mt-1 truncate font-semibold text-slate-700">{employee.work_location || 'Not set'}</dd></div>
                </dl>
              </Link>
            </Card>
          ))}
        </div>
      )}

      {hasPermission('employee:update') && (
        <div className="flex justify-end"><Link to="/departments" className="inline-flex items-center gap-1.5 text-sm font-semibold text-blue-700 hover:text-blue-900"><Building2 size={15} /> Manage departments</Link></div>
      )}

      <Modal title="Create employee" description="Add the employee’s core employment and reporting information." open={open} onClose={() => setOpen(false)}>
        <EmployeeForm onSubmit={create} loading={saving} employees={employeeOptions} departments={departments} />
      </Modal>
      <Modal title="Change department" description="This change is applied to every selected employee." open={transferOpen} onClose={() => setTransferOpen(false)}>
        <DepartmentTransferModal employees={selectedEmployees} departments={departments} loading={saving} onSubmit={transfer} />
      </Modal>
    </div>
  );
}
