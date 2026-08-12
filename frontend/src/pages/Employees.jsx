import { useCallback, useEffect, useMemo, useState } from 'react';
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
import Pagination from '../components/ui/Pagination.jsx';
import Select from '../components/ui/Select.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import Table from '../components/ui/Table.jsx';
import usePermissions from '../hooks/usePermissions';

export default function Employees() {
  const [employees, setEmployees] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [summary, setSummary] = useState({
    total: 0,
    active: 0,
    departments: 0,
    work_locations: 0,
  });
  const [meta, setMeta] = useState({
    page: 1,
    per_page: 15,
    total: 0,
    pages: 1,
  });
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
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState({
    key: 'full_name',
    direction: 'asc',
  });
  const [view, setView] = useState('list');
  const { hasPermission } = usePermissions();

  const loadReferenceData = useCallback(async () => {
    try {
      const [departmentResponse, optionResponse] = await Promise.all([
        departmentApi.list(),
        employeeApi.options(),
      ]);
      setDepartments(departmentResponse.data.items || []);
      setEmployeeOptions(optionResponse.data.items || []);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to load employee reference data',
      );
    }
  }, []);

  const loadSummary = useCallback(async () => {
    try {
      const response = await employeeApi.summary();
      setSummary(response.data);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to load workforce totals',
      );
    }
  }, []);

  const loadEmployees = useCallback(async () => {
    setLoading(true);
    try {
      const response = await employeeApi.list({
        page,
        per_page: 15,
        q: query || undefined,
        status: status || undefined,
        department_id: department || undefined,
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
      setError(
        err.error?.message
        || 'Unable to load people directory',
      );
    } finally {
      setLoading(false);
    }
  }, [department, page, query, sort, status]);

  useEffect(() => {
    loadReferenceData();
    loadSummary();
  }, [loadReferenceData, loadSummary]);

  useEffect(() => {
    loadEmployees();
  }, [loadEmployees]);

  const departmentNames = useMemo(
    () => Object.fromEntries(
      departments.map((item) => [item.id, item.name]),
    ),
    [departments],
  );
  const selectedEmployees = useMemo(
    () => employeeOptions.filter(
      (employee) => selectedIds.has(employee.id),
    ),
    [employeeOptions, selectedIds],
  );

  const hasFilters = Boolean(query || status || department);

  const refreshDirectory = async () => {
    await Promise.all([
      loadEmployees(),
      loadSummary(),
      loadReferenceData(),
    ]);
  };

  const create = async (payload) => {
    setSaving(true);
    setError('');
    try {
      await employeeApi.create(payload);
      setOpen(false);
      setMessage('Employee created.');
      await refreshDirectory();
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
      setMessage(
        response.message
        || `${selectedEmployees.length} employee(s) transferred.`,
      );
      setSelectedIds(new Set());
      setTransferOpen(false);
      await refreshDirectory();
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

  const allVisibleSelected = employees.length > 0
    && employees.every((employee) => selectedIds.has(employee.id));
  const toggleVisible = () => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (allVisibleSelected) {
        employees.forEach((employee) => next.delete(employee.id));
      } else {
        employees.forEach((employee) => next.add(employee.id));
      }
      return next;
    });
  };

  const resetFilters = () => {
    setQuery('');
    setStatus('');
    setDepartment('');
    setPage(1);
  };

  const updateQuery = (value) => {
    setQuery(value);
    setPage(1);
  };

  const updateStatus = (value) => {
    setStatus(value);
    setPage(1);
  };

  const updateDepartment = (value) => {
    setDepartment(value);
    setPage(1);
  };

  const updateSort = (value) => {
    setSort(value);
    setPage(1);
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
        <StatCard label="Headcount" value={summary.total} detail={`${summary.active} active employees`} icon={UsersRound} tone="blue" />
        <StatCard label="Departments" value={summary.departments} detail="Organizational teams" icon={Building2} tone="violet" />
        <StatCard label="Work locations" value={summary.work_locations} detail="Workforce footprint" icon={Network} tone="emerald" />
      </div>

      <Card padded={false}>
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 lg:flex-row lg:items-center">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-3 text-slate-400" size={17} />
            <Input aria-label="Search people" className="pl-9" placeholder="Search people, job titles, or locations" value={query} onChange={(event) => updateQuery(event.target.value)} />
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:flex">
            <Select aria-label="Employment status" className="lg:w-44" value={status} onChange={(event) => updateStatus(event.target.value)}>
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="probation">Probation</option>
              <option value="inactive">Inactive</option>
              <option value="suspended">Suspended</option>
              <option value="terminated">Terminated</option>
            </Select>
            <Select aria-label="Department" className="lg:w-52" value={department} onChange={(event) => updateDepartment(event.target.value)}>
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
          <span className="inline-flex items-center gap-1.5"><SlidersHorizontal size={14} /> Showing {employees.length} of {meta.total} matching people</span>
          {hasPermission('employee:update') && employees.length > 0 && (
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
        <Table
          columns={columns}
          rows={employees}
          loading={loading}
          empty={hasFilters ? 'No people match these filters.' : 'No employee records yet.'}
          caption="People directory"
          sort={sort}
          onSortChange={updateSort}
          pagination={{
            page: meta.page,
            pageSize: meta.per_page,
            total: meta.total,
            onPageChange: setPage,
            label: 'people',
          }}
        />
      ) : loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, index) => <div key={index} className="h-52 animate-pulse rounded-xl bg-slate-200" />)}</div>
      ) : employees.length === 0 ? (
        <EmptyState title="No people match these filters" description="Clear the filters or add a new employee record." icon={UsersRound} />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {employees.map((employee) => (
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
          {meta.total > 0 && (
            <Pagination
              page={meta.page}
              pageSize={meta.per_page}
              total={meta.total}
              onPageChange={setPage}
              label="people"
            />
          )}
        </>
      )}

      {hasPermission('employee:update') && (
        <div className="flex justify-end"><Link to="/departments" className="inline-flex items-center gap-1.5 text-sm font-semibold text-blue-700 hover:text-blue-900"><Building2 size={15} /> Manage departments</Link></div>
      )}

      <Modal
        title="Create employee"
        description="Add the employee’s core employment and reporting information."
        open={open}
        onClose={() => setOpen(false)}
        size="xl"
        footer={
          <>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setOpen(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="create-employee-form"
              disabled={saving}
              className="min-w-36"
            >
              {saving ? 'Saving...' : 'Save employee'}
            </Button>
          </>
        }
      >
        <EmployeeForm
          formId="create-employee-form"
          showActions={false}
          onSubmit={create}
          loading={saving}
          employees={employeeOptions}
          departments={departments}
        />
      </Modal>
      <Modal title="Change department" description="This change is applied to every selected employee." open={transferOpen} onClose={() => setTransferOpen(false)}>
        <DepartmentTransferModal employees={selectedEmployees} departments={departments} loading={saving} onSubmit={transfer} />
      </Modal>
    </div>
  );
}
