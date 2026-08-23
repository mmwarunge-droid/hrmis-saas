import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Briefcase,
  CalendarClock,
  CalendarDays,
  Clock,
  FileText,
  History,
  KeyRound,
  Mail,
  MapPin,
  Pencil,
  Phone,
  ShieldCheck,
  Target,
  UserRoundCheck,
  WalletCards,
} from 'lucide-react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { attendanceApi } from '../api/attendanceApi.js';
import { documentApi } from '../api/documentApi.js';
import { employeeApi } from '../api/employeeApi';
import { leaveApi } from '../api/leaveApi.js';
import { goalApi } from '../api/goalApi.js';
import { userApi } from '../api/userApi.js';
import EmployeeAccessForm from '../components/employees/EmployeeAccessForm.jsx';
import EmployeeAccountLinkForm from '../components/employees/EmployeeAccountLinkForm.jsx';
import EmployeeForm from '../components/employees/EmployeeForm.jsx';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import Modal from '../components/ui/Modal.jsx';
import Skeleton from '../components/ui/Skeleton.jsx';
import Table from '../components/ui/Table.jsx';
import Tabs from '../components/ui/Tabs.jsx';
import usePermissions from '../hooks/usePermissions.js';

function formatDate(value, fallback = 'Not set') {
  if (!value) return fallback;
  return new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T00:00:00`));
}

function formatTime(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('en', { hour: '2-digit', minute: '2-digit' }).format(new Date(value));
}

function toneForStatus(status) {
  if (['active', 'approved', 'signed'].includes(status)) return 'green';
  if (['probation', 'pending', 'pending_review'].includes(status)) return 'amber';
  if (['terminated', 'rejected', 'declined', 'expired'].includes(status)) return 'red';
  return 'slate';
}

function DetailRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-3 py-2.5">
      <Icon size={15} className="mt-0.5 shrink-0 text-slate-400" />
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-slate-400">{label}</p>
        <p className="mt-0.5 break-words text-sm font-medium text-slate-700">{value || 'Not set'}</p>
      </div>
    </div>
  );
}

export default function EmployeeDetails() {
  const { hasPermission } = usePermissions();
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [employee, setEmployee] = useState(null);
  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [history, setHistory] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [leaveRequests, setLeaveRequests] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [goals, setGoals] = useState([]);
  const [open, setOpen] = useState(false);
  const [accessOpen, setAccessOpen] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [userOptions, setUserOptions] = useState([]);
  const [saving, setSaving] = useState(false);
  const [accessSaving, setAccessSaving] = useState(false);
  const [linkSaving, setLinkSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const canReadDocuments = hasPermission('document:read');
  const canReadLeave = hasPermission('leave:create');
  const canReadAttendance = hasPermission('attendance:read');
  const canReadGoals = hasPermission('goal:read');
  const activeTab = searchParams.get('tab') || 'personal';

  const load = useCallback(async () => {
    setError('');
    try {
      const [employeeResponse, optionResponse, departmentResponse, historyResponse] = await Promise.all([
        employeeApi.get(id),
        employeeApi.options(),
        employeeApi.departments(),
        employeeApi.history(id),
      ]);
      setEmployee(employeeResponse.data);
      setEmployeeOptions(optionResponse.data.items || []);
      setDepartments(departmentResponse.data.items || []);
      setHistory(historyResponse.data.items || []);

      const [documentsResult, leaveResult, attendanceResult, goalsResult] = await Promise.allSettled([
        canReadDocuments ? documentApi.list({ employee_id: id, per_page: 100 }) : Promise.resolve({ data: { items: [] } }),
        canReadLeave ? leaveApi.requests({ employee_id: id, per_page: 100 }) : Promise.resolve({ data: { items: [] } }),
        canReadAttendance ? attendanceApi.list({ employee_id: id, per_page: 100 }) : Promise.resolve({ data: { items: [] } }),
        canReadGoals ? goalApi.list({ employee_id: id, per_page: 100 }) : Promise.resolve({ data: { items: [] } }),
      ]);

      setDocuments(documentsResult.status === 'fulfilled' ? documentsResult.value.data.items || [] : []);
      setLeaveRequests(leaveResult.status === 'fulfilled' ? leaveResult.value.data.items || [] : []);
      setAttendance(attendanceResult.status === 'fulfilled' ? attendanceResult.value.data.items || [] : []);
      setGoals(goalsResult.status === 'fulfilled' ? goalsResult.value.data.items || [] : []);
    } catch (err) {
      setError(err.error?.message || 'Employee not found');
    } finally {
      setLoading(false);
    }
  }, [canReadAttendance, canReadDocuments, canReadGoals, canReadLeave, id]);

  useEffect(() => { load(); }, [load]);

  const employeeNames = useMemo(
    () => Object.fromEntries(employeeOptions.map((item) => [item.id, item.full_name])),
    [employeeOptions],
  );
  const departmentNames = useMemo(
    () => Object.fromEntries(departments.map((item) => [item.id, item.name])),
    [departments],
  );

  const activityItems = useMemo(() => [
    ...history.map((item) => ({
      id: `job-${item.id}`,
      type: 'job',
      date: item.start_date || item.created_at,
      title: item.job_title ? `Job updated to ${item.job_title}` : 'Employment details updated',
      detail: item.reason || item.department_name || 'Employment history changed.',
      status: null,
    })),
    ...leaveRequests.map((item) => ({
      id: `leave-${item.id}`,
      type: 'leave',
      date: item.created_at || item.start_date,
      title: `Time-off request ${String(item.status || 'submitted').replaceAll('_', ' ')}`,
      detail: `${formatDate(item.start_date)} – ${formatDate(item.end_date)}${item.reason ? ` · ${item.reason}` : ''}`,
      status: item.status,
    })),
    ...documents.map((item) => ({
      id: `file-${item.id}`,
      type: 'file',
      date: item.created_at || item.issue_date,
      title: `File added: ${item.title}`,
      detail: item.document_type?.replaceAll('_', ' ') || item.original_filename || 'Employee file',
      status: item.signature_status,
    })),
    ...goals.map((item) => ({
      id: `goal-${item.id}`,
      type: 'goal',
      date: item.last_check_in_at || item.updated_at || item.created_at,
      title: `Goal progress: ${item.title}`,
      detail: `${Math.round(item.progress_percent)}% complete · ${String(item.health).replaceAll('_', ' ')}`,
      status: item.health,
    })),
    ...attendance.map((item) => ({
      id: `attendance-${item.id}`,
      type: 'attendance',
      date: item.work_date,
      title: 'Attendance recorded',
      detail: `${formatTime(item.check_in_at)} – ${formatTime(item.check_out_at)}`,
      status: item.check_out_at ? 'complete' : item.check_in_at ? 'in progress' : null,
    })),
  ].filter((item) => item.date).sort((left, right) => new Date(right.date) - new Date(left.date)), [attendance, documents, goals, history, leaveRequests]);

  const update = async (payload) => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const response = await employeeApi.update(id, payload);
      await load();
      setOpen(false);
      setSuccess(response.message || 'Employment details updated.');
    } catch (err) {
      setError(err.error?.message || 'Employee update failed');
    } finally {
      setSaving(false);
    }
  };

  const openLink = async () => {
    setError('');
    try {
      const response = await userApi.options();
      setUserOptions(response.data.items || []);
      setLinkOpen(true);
    } catch (err) {
      setError(err.error?.message || 'Unable to load user accounts.');
    }
  };

  const linkAccount = async (userId) => {
    setLinkSaving(true);
    setError('');
    try {
      await userApi.linkEmployee(userId, employee.id);
      setLinkOpen(false);
      setSuccess('Existing user account linked to this employee.');
      await load();
    } catch (err) {
      setError(err.error?.message || 'Account linking failed.');
    } finally {
      setLinkSaving(false);
    }
  };

  const provisionAccess = async (payload) => {
    setAccessSaving(true);
    setError('');
    setSuccess('');
    try {
      const response = await employeeApi.provisionAccess(id, payload);
      setEmployee(response.data.employee);
      setAccessOpen(false);
      setSuccess(`Access was provisioned for ${response.data.user.email}.`);
    } catch (err) {
      setError(err.error?.message || 'Access provisioning failed');
    } finally {
      setAccessSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-64 w-full" />
        <div className="grid gap-5 lg:grid-cols-[260px_1fr]"><Skeleton className="h-80" /><Skeleton className="h-96" /></div>
      </div>
    );
  }
  if (error && !employee) return <Alert type="error">{error}</Alert>;
  if (!employee) return null;

  const canProvisionAccess = hasPermission('user:create') && hasPermission('employee:update');
  const tabs = [
    { value: 'personal', label: 'Personal' },
    { value: 'job', label: 'Job' },
    { value: 'time-off', label: 'Time off', count: leaveRequests.length },
    { value: 'attendance', label: 'Attendance', count: attendance.length },
    { value: 'files', label: 'Files', count: documents.length },
    { value: 'payroll', label: 'Payroll' },
    { value: 'performance', label: 'Performance', count: goals.length },
    { value: 'notes', label: 'Notes' },
    { value: 'activity', label: 'Activity', count: activityItems.length },
  ];

  const setTab = (value) => setSearchParams(value === 'personal' ? {} : { tab: value }, { replace: true });

  const leaveColumns = [
    { key: 'start_date', label: 'Dates', sortable: true, render: (row) => `${formatDate(row.start_date)} – ${formatDate(row.end_date)}` },
    { key: 'total_days', label: 'Days', sortable: true },
    { key: 'reason', label: 'Reason', render: (row) => row.reason || '—' },
    { key: 'status', label: 'Status', sortable: true, render: (row) => <Badge tone={toneForStatus(row.status)}>{row.status}</Badge> },
  ];
  const attendanceColumns = [
    { key: 'work_date', label: 'Work date', sortable: true, render: (row) => formatDate(row.work_date) },
    { key: 'check_in_at', label: 'Check in', render: (row) => formatTime(row.check_in_at) },
    { key: 'check_out_at', label: 'Check out', render: (row) => formatTime(row.check_out_at) },
    { key: 'source', label: 'Source', render: (row) => <Badge>{row.source?.replaceAll('_', ' ') || '—'}</Badge> },
  ];
  const documentColumns = [
    { key: 'title', label: 'File', sortable: true, render: (row) => <div><p className="font-semibold text-slate-900">{row.title}</p><p className="text-xs text-slate-500">{row.original_filename}</p></div> },
    { key: 'document_type', label: 'Type', sortable: true, render: (row) => <Badge tone="blue">{row.document_type}</Badge> },
    { key: 'signature_status', label: 'Signature', sortable: true, render: (row) => <Badge tone={toneForStatus(row.signature_status)}>{row.signature_status?.replaceAll('_', ' ') || 'Not required'}</Badge> },
    { key: 'expiry_date', label: 'Expiry', sortable: true, render: (row) => formatDate(row.expiry_date, '—') },
    { key: 'download', label: '', render: (row) => <a href={`/documents/${row.id}/review`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700 hover:text-blue-900">Review</a> },
  ];

  const goalColumns = [
    { key: 'title', label: 'Goal', sortable: true, render: (row) => <div><p className="font-semibold text-slate-900">{row.title}</p><p className="text-xs capitalize text-slate-500">{row.owner_type} goal</p></div> },
    { key: 'progress_percent', label: 'Progress', sortable: true, render: (row) => <div className="min-w-36"><div className="flex justify-between text-xs"><span className="font-semibold text-slate-700">{Math.round(row.progress_percent)}%</span><span className="text-slate-500">{row.current_value}/{row.target_value} {row.unit}</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: `${Math.min(100, Math.max(0, row.progress_percent))}%` }} /></div></div> },
    { key: 'health', label: 'Health', sortable: true, render: (row) => <Badge tone={row.health === 'on_track' || row.health === 'completed' ? 'green' : row.health === 'at_risk' ? 'amber' : 'red'}>{row.health.replaceAll('_', ' ')}</Badge> },
    { key: 'due_date', label: 'Due', sortable: true, render: (row) => formatDate(row.due_date) },
  ];


  return (
    <div className="space-y-5 pb-8">
      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      <Card padded={false} className="overflow-hidden">
        <div
          className="h-32 bg-gradient-to-r from-blue-800 via-blue-700 to-sky-600 md:h-40"
          style={employee.profile_cover_url ? {
            backgroundImage: `linear-gradient(90deg, rgba(30,64,175,.55), rgba(3,105,161,.25)), url(${employee.profile_cover_url})`,
            backgroundPosition: 'center',
            backgroundSize: 'cover',
          } : undefined}
        />
        <div className="px-5 md:px-6">
          <div className="-mt-10 flex flex-col gap-4 pb-5 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex min-w-0 items-end gap-4">
              <Avatar name={employee.full_name} src={employee.profile_photo_url} size="xl" className="ring-4 ring-white" />
              <div className="min-w-0 pb-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="truncate text-2xl font-bold tracking-[-0.025em] text-slate-950">{employee.full_name}</h1>
                  <Badge tone={toneForStatus(employee.employment_status)}>{employee.employment_status}</Badge>
                </div>
                <p className="mt-1 truncate text-sm font-medium text-slate-600">
                  {employee.job_title || 'Role not assigned'}
                  {departmentNames[employee.department_id] ? ` · ${departmentNames[employee.department_id]}` : ''}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {!employee.user_id && canProvisionAccess && employee.employment_status !== 'terminated' && (
                <>
                  <Button variant="secondary" onClick={() => setAccessOpen(true)}><KeyRound size={15} /> Provision access</Button>
                  <Button variant="ghost" onClick={openLink}><UserRoundCheck size={15} /> Link existing</Button>
                </>
              )}
              {hasPermission('employee:update') && (
                <Button onClick={() => setOpen(true)}><Pencil size={15} /> Edit employee</Button>
              )}
            </div>
          </div>
          <Tabs items={tabs} value={activeTab} onChange={setTab} ariaLabel="Employee profile sections" idPrefix="employee-sections" />
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card>
            <h2 className="text-sm font-bold text-slate-950">Employee summary</h2>
            <div className="mt-3 divide-y divide-slate-100">
              <DetailRow icon={Mail} label="Work email" value={employee.email} />
              <DetailRow icon={Phone} label="Phone" value={employee.phone} />
              <DetailRow icon={MapPin} label="Location" value={employee.work_location} />
              <DetailRow icon={UserRoundCheck} label="Reports to" value={employeeNames[employee.manager_id] || 'Top level'} />
              <DetailRow icon={CalendarClock} label="Hire date" value={formatDate(employee.hire_date)} />
              <DetailRow icon={ShieldCheck} label="Access" value={employee.user_id ? 'Enabled' : 'Not provisioned'} />
            </div>
          </Card>
          <Card>
            <h2 className="text-sm font-bold text-slate-950">Employee ID</h2>
            <p className="mt-2 font-mono text-sm text-slate-700">{employee.employee_number || 'Not set'}</p>
            <p className="mt-3 text-xs leading-5 text-slate-500">Use this identifier when reconciling records with connected payroll or HR systems.</p>
          </Card>
        </aside>

        <div id={`employee-sections-panel-${activeTab}`} role="tabpanel" aria-labelledby={`employee-sections-tab-${activeTab}`} tabIndex={0} className="min-w-0">
          {activeTab === 'personal' && (
            <div className="space-y-5">
              <Card>
                <div className="flex items-center gap-3">
                  <span className="grid h-9 w-9 place-items-center rounded-lg border border-blue-100 bg-blue-50 text-blue-700"><Mail size={17} /></span>
                  <div><p className="text-[11px] font-bold uppercase tracking-[0.13em] text-blue-700">Personal</p><h2 className="text-lg font-bold text-slate-950">Basic information</h2></div>
                </div>
                <dl className="mt-5 grid gap-x-8 gap-y-5 sm:grid-cols-2">
                  {[
                    ['First name', employee.first_name],
                    ['Preferred name', employee.preferred_name || 'Not set'],
                    ['Last name', employee.last_name],
                    ['Date of birth', formatDate(employee.date_of_birth)],
                    ['Email', employee.email],
                    ['Phone', employee.phone || 'Not set'],
                    ['Address', employee.address || 'Not set'],
                    ['Work location', employee.work_location || 'Not set'],
                  ].map(([label, value]) => <div key={label}><dt className="text-xs font-semibold text-slate-500">{label}</dt><dd className="mt-1 text-sm font-medium text-slate-900">{value}</dd></div>)}
                </dl>
              </Card>

              <Card>
                <h2 className="text-lg font-bold text-slate-950">About</h2>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">{employee.biography || 'No introduction has been added yet.'}</p>
                <div className="mt-5 flex flex-wrap gap-2">
                  {(employee.hobbies || []).length > 0
                    ? employee.hobbies.map((hobby) => <Badge key={hobby} tone="blue">{hobby}</Badge>)
                    : <span className="text-sm text-slate-500">No interests added.</span>}
                </div>
              </Card>
            </div>
          )}

          {activeTab === 'job' && (
            <div className="space-y-5">
              <Card>
                <div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-lg border border-blue-100 bg-blue-50 text-blue-700"><Briefcase size={17} /></span><div><p className="text-[11px] font-bold uppercase tracking-[0.13em] text-blue-700">Job</p><h2 className="text-lg font-bold text-slate-950">Employment details</h2></div></div>
                <dl className="mt-5 grid gap-x-8 gap-y-5 sm:grid-cols-2 xl:grid-cols-3">
                  {[
                    ['Employment status', employee.employment_status],
                    ['Employment type', employee.employment_type?.replaceAll('_', ' ') || 'Not set'],
                    ['Job title', employee.job_title || 'Not assigned'],
                    ['Department', departmentNames[employee.department_id] || 'Unassigned'],
                    ['Manager', employeeNames[employee.manager_id] || 'Top level'],
                    ['Hire date', formatDate(employee.hire_date)],
                    ['Termination date', formatDate(employee.termination_date)],
                    ['External HRIS ID', employee.external_hris_id || 'Not set'],
                  ].map(([label, value]) => <div key={label}><dt className="text-xs font-semibold text-slate-500">{label}</dt><dd className="mt-1 text-sm font-medium capitalize text-slate-900">{value}</dd></div>)}
                </dl>
              </Card>

              <Card>
                <div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-lg border border-blue-100 bg-blue-50 text-blue-700"><History size={17} /></span><div><h2 className="text-lg font-bold text-slate-950">Employment history</h2><p className="text-sm text-slate-500">Promotions, reporting changes, and department transfers.</p></div></div>
                <div className="relative mt-5 space-y-0 border-l border-slate-200 pl-5">
                  {history.length === 0 ? <EmptyState title="No employment changes recorded" description="Future job, manager, and department changes will appear here." icon={History} /> : history.map((item) => (
                    <div key={item.id} className="relative pb-6 last:pb-0">
                      <span className="absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-blue-600 ring-1 ring-blue-200" />
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div><p className="font-semibold text-slate-900">{item.job_title || 'Unassigned role'}</p><p className="mt-1 text-sm text-slate-600">{item.department_name || 'No department'}{item.manager_name ? ` · Reports to ${item.manager_name}` : ' · Top level'}</p></div>
                        <span className="text-xs font-medium text-slate-500">{formatDate(item.start_date)}{item.end_date ? ` – ${formatDate(item.end_date)}` : ' – Present'}</span>
                      </div>
                      {item.reason && <p className="mt-2 text-sm text-slate-500">{item.reason}</p>}
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {activeTab === 'time-off' && (
            <Card>
              <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-[11px] font-bold uppercase tracking-[0.13em] text-blue-700">Time off</p><h2 className="mt-1 text-lg font-bold text-slate-950">Request history</h2><p className="mt-1 text-sm text-slate-500">Approved, pending, rejected, and cancelled requests.</p></div><Link to="/leave"><Button variant="secondary" size="sm"><CalendarDays size={15} /> Open time off</Button></Link></div>
              <div className="mt-5">{canReadLeave ? <Table columns={leaveColumns} rows={leaveRequests} pageSize={10} empty="No time-off requests for this employee." /> : <EmptyState title="Time-off access is restricted" description="Your current role cannot view this employee’s time-off history." icon={CalendarDays} />}</div>
            </Card>
          )}

          {activeTab === 'attendance' && (
            <Card>
              <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-[11px] font-bold uppercase tracking-[0.13em] text-blue-700">Attendance</p><h2 className="mt-1 text-lg font-bold text-slate-950">Attendance records</h2><p className="mt-1 text-sm text-slate-500">Recorded check-in and check-out activity.</p></div><Link to="/attendance"><Button variant="secondary" size="sm"><Clock size={15} /> Open attendance</Button></Link></div>
              <div className="mt-5">{canReadAttendance ? <Table columns={attendanceColumns} rows={attendance} pageSize={10} empty="No attendance records for this employee." /> : <EmptyState title="Attendance access is restricted" description="Your current role cannot view attendance records." icon={Clock} />}</div>
            </Card>
          )}

          {activeTab === 'files' && (
            <Card>
              <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-[11px] font-bold uppercase tracking-[0.13em] text-blue-700">Files</p><h2 className="mt-1 text-lg font-bold text-slate-950">Employee documents</h2><p className="mt-1 text-sm text-slate-500">Contracts, policies, certificates, and signed records linked to this employee.</p></div><Link to="/documents"><Button variant="secondary" size="sm"><FileText size={15} /> Open files</Button></Link></div>
              <div className="mt-5">{canReadDocuments ? <Table columns={documentColumns} rows={documents} pageSize={10} empty="No files are linked to this employee." /> : <EmptyState title="File access is restricted" description="Your current role cannot view employee files." icon={FileText} />}</div>
            </Card>
          )}

          {activeTab === 'payroll' && (
            <Card><EmptyState title="Payroll is not connected" description="The current service architecture does not expose payroll records. This workspace is ready for a future payroll integration without changing the employee profile hierarchy." icon={WalletCards} /></Card>
          )}

          {activeTab === 'performance' && (
            <Card>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div><p className="text-[11px] font-bold uppercase tracking-[0.13em] text-blue-700">Performance</p><h2 className="mt-1 text-lg font-bold text-slate-950">Goals & KPI progress</h2><p className="mt-1 text-sm text-slate-500">Measurable outcomes assigned directly to this employee.</p></div>
                <Link to="/goals"><Button variant="secondary" size="sm"><Target size={15} /> Open goals</Button></Link>
              </div>
              <div className="mt-5">{canReadGoals ? <Table columns={goalColumns} rows={goals} pageSize={10} empty="No goals are assigned to this employee." /> : <EmptyState title="Performance access is restricted" description="Your current role cannot view this employee’s goals." icon={Target} />}</div>
            </Card>
          )}

          {activeTab === 'notes' && (
            <Card>
              <div><p className="text-[11px] font-bold uppercase tracking-[0.13em] text-blue-700">Notes</p><h2 className="mt-1 text-lg font-bold text-slate-950">Change notes and activity context</h2><p className="mt-1 text-sm text-slate-500">Reasons captured when employment details changed.</p></div>
              <div className="mt-5 space-y-3">
                {history.filter((item) => item.reason).length === 0 ? <EmptyState title="No notes recorded" description="Change reasons will appear here when administrators update employment details." icon={FileText} /> : history.filter((item) => item.reason).map((item) => (
                  <div key={item.id} className="rounded-lg border border-slate-200 p-4"><div className="flex items-center justify-between gap-3"><p className="text-sm font-semibold text-slate-900">{item.job_title || 'Employment change'}</p><span className="text-xs text-slate-500">{formatDate(item.start_date)}</span></div><p className="mt-2 text-sm leading-6 text-slate-600">{item.reason}</p></div>
                ))}
              </div>
            </Card>
          )}

          {activeTab === 'activity' && (
            <Card>
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.13em] text-blue-700">Activity</p>
                <h2 className="mt-1 text-lg font-bold text-slate-950">Employee timeline</h2>
                <p className="mt-1 text-sm text-slate-500">Recent employment, time-off, attendance, and file activity available through existing APIs.</p>
              </div>
              <div className="relative mt-6 border-l border-slate-200 pl-6">
                {activityItems.length === 0 ? (
                  <EmptyState title="No employee activity yet" description="Employment changes and employee workflow activity will appear here." icon={History} />
                ) : activityItems.slice(0, 25).map((item) => {
                  const ActivityIcon = item.type === 'leave'
                    ? CalendarDays
                    : item.type === 'file'
                      ? FileText
                      : item.type === 'attendance'
                        ? Clock
                        : item.type === 'goal'
                          ? Target
                          : Briefcase;
                  return (
                    <div key={item.id} className="relative pb-6 last:pb-0">
                      <span className="absolute -left-[39px] top-0 grid h-7 w-7 place-items-center rounded-full border border-blue-100 bg-blue-50 text-blue-700 ring-4 ring-white">
                        <ActivityIcon size={14} />
                      </span>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                          <p className="mt-1 text-sm leading-6 text-slate-600">{item.detail}</p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          {item.status && <Badge tone={toneForStatus(item.status)}>{String(item.status).replaceAll('_', ' ')}</Badge>}
                          <span className="text-xs font-medium text-slate-500">{formatDate(String(item.date).slice(0, 10))}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}
        </div>
      </div>

      <Modal title={`Edit ${employee.full_name}`} description="Update employment data while preserving the effective-date history." open={open} onClose={() => setOpen(false)} size="xl">
        <EmployeeForm onSubmit={update} loading={saving} initialValues={employee} employees={employeeOptions} departments={departments} excludeEmployeeId={employee.id} submitLabel="Update employee" showChangeContext />
      </Modal>
      <Modal title={`Provision access for ${employee.full_name}`} description="Create a linked Kinetic account for this employee record." open={accessOpen} onClose={() => setAccessOpen(false)} size="lg">
        <EmployeeAccessForm employee={employee} onSubmit={provisionAccess} loading={accessSaving} />
      </Modal>
      <Modal title={`Link existing account to ${employee.full_name}`} description="Connect a tenant user to this employee record without creating another identity." open={linkOpen} onClose={() => setLinkOpen(false)} size="lg">
        <EmployeeAccountLinkForm employee={employee} users={userOptions} onSubmit={linkAccount} loading={linkSaving} />
      </Modal>
    </div>
  );
}
