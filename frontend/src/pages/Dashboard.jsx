import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BriefcaseBusiness,
  CalendarDays,
  CheckCircle2,
  FileWarning,
  Network,
  Sparkles,
  UserPlus,
  UsersRound,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { dashboardApi } from '../api/dashboardApi';
import { employeeApi } from '../api/employeeApi';
import { leaveApi } from '../api/leaveApi';
import { onboardingApi } from '../api/onboardingApi';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import ProgressRing from '../components/ui/ProgressRing.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import useAuth from '../hooks/useAuth.js';
import usePermissions from '../hooks/usePermissions.js';

const settleData = (result, fallback) => result.status === 'fulfilled' ? result.value.data : fallback;

function formatDate(value) {
  if (!value) return 'No date';
  return new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short' }).format(new Date(`${value}T00:00:00`));
}

export default function Dashboard() {
  const { user } = useAuth();
  const { hasPermission } = usePermissions();
  const [summary, setSummary] = useState(null);
  const [alerts, setAlerts] = useState({ expiring_documents: [], employees_missing_contracts: [] });
  const [employees, setEmployees] = useState([]);
  const [leaveRequests, setLeaveRequests] = useState([]);
  const [leaveSummary, setLeaveSummary] = useState({});
  const [tasks, setTasks] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    const requests = [
      dashboardApi.summary(),
      dashboardApi.complianceAlerts(),
      employeeApi.list(),
      dashboardApi.leaveSummary(),
      leaveApi.requests(),
      onboardingApi.myTasks(),
    ];
    Promise.allSettled(requests).then((results) => {
      const [summaryResult, alertsResult, employeesResult, leaveSummaryResult, requestsResult, tasksResult] = results;
      setSummary(settleData(summaryResult, null));
      setAlerts(settleData(alertsResult, { expiring_documents: [], employees_missing_contracts: [] }));
      setEmployees(settleData(employeesResult, { items: [] }).items || []);
      setLeaveSummary(settleData(leaveSummaryResult, { by_status: {} }).by_status || {});
      setLeaveRequests(settleData(requestsResult, { items: [] }).items || []);
      setTasks(settleData(tasksResult, { items: [] }).items || []);
      if (summaryResult.status === 'rejected') setError(summaryResult.reason?.error?.message || 'Some dashboard data could not be loaded');
    });
  }, []);

  const activeEmployees = employees.filter((employee) => employee.employment_status === 'active').length;
  const peopleHealth = employees.length ? Math.round((activeEmployees / employees.length) * 100) : 0;
  const pendingTasks = tasks.filter((task) => !['completed', 'waived'].includes(task.status)).length;
  const pendingLeave = leaveSummary.pending || summary?.pending_leave_requests || 0;
  const approvedUpcoming = leaveRequests
    .filter((request) => request.status === 'approved' && new Date(`${request.end_date}T23:59:59`) >= new Date())
    .sort((a, b) => a.start_date.localeCompare(b.start_date))
    .slice(0, 5);
  const recentHires = useMemo(() => [...employees].filter((item) => item.hire_date).sort((a, b) => b.hire_date.localeCompare(a.hire_date)).slice(0, 5), [employees]);
  const complianceCount = (alerts.expiring_documents?.length || 0) + (alerts.employees_missing_contracts?.length || 0);

  const quickActions = [
    hasPermission('leave:create') && { to: '/leave', label: 'Request time off', icon: CalendarDays, tone: 'bg-cyan-50 text-cyan-700' },
    hasPermission('employee:create') && { to: '/employees', label: 'Add a person', icon: UserPlus, tone: 'bg-violet-50 text-violet-700' },
    hasPermission('document:upload') && { to: '/documents', label: 'Upload documents', icon: FileWarning, tone: 'bg-amber-50 text-amber-700' },
    hasPermission('onboarding:assign') && { to: '/tasks', label: 'Review tasks', icon: CheckCircle2, tone: 'bg-emerald-50 text-emerald-700' },
  ].filter(Boolean);

  if (!summary && !error) return <div className="h-80 animate-pulse rounded-[2rem] bg-slate-100" />;

  return (
    <div className="space-y-7">
      <section className="relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-slate-950 via-blue-950 to-cyan-900 p-6 text-white shadow-2xl md:p-8">
        <div className="absolute -right-16 -top-20 h-64 w-64 rounded-full bg-cyan-400/20 blur-3xl" />
        <div className="absolute bottom-0 right-1/4 h-40 w-40 rounded-full bg-violet-500/20 blur-3xl" />
        <div className="relative grid gap-8 xl:grid-cols-[1.3fr_0.7fr] xl:items-end">
          <div>
            <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.22em] text-cyan-200"><Sparkles size={15} /> People workspace</p>
            <h1 className="mt-4 max-w-3xl text-3xl font-bold tracking-tight md:text-5xl">Hi {user?.first_name || 'there'}, keep your people moving forward.</h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-300">Your operational view of people, leave, documents, onboarding and compliance—designed for action rather than administration.</p>
            <div className="mt-6 flex flex-wrap gap-3">
              {quickActions.slice(0, 3).map(({ to, label, icon: Icon }) => <Link key={to + label} to={to}><Button variant="secondary" className="border-white/10 bg-white/10 text-white hover:bg-white/20"><Icon size={16} /> {label}</Button></Link>)}
            </div>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/10 p-5 backdrop-blur">
            <p className="text-xs font-bold uppercase tracking-wider text-cyan-200">Today’s focus</p>
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between"><span className="text-sm text-slate-200">Pending leave approvals</span><strong>{pendingLeave}</strong></div>
              <div className="flex items-center justify-between"><span className="text-sm text-slate-200">Open onboarding tasks</span><strong>{pendingTasks}</strong></div>
              <div className="flex items-center justify-between"><span className="text-sm text-slate-200">Compliance alerts</span><strong>{complianceCount}</strong></div>
            </div>
          </div>
        </div>
      </section>

      {error && <Alert type="error">{error}</Alert>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="People" value={summary?.employees ?? employees.length} detail={`${activeEmployees} active · ${employees.length - activeEmployees} other`} icon={UsersRound} tone="blue" />
        <StatCard label="Documents" value={summary?.documents ?? 0} detail={`${alerts.expiring_documents?.length || 0} expiring in 30 days`} icon={BriefcaseBusiness} tone="violet" />
        <StatCard label="Pending leave" value={pendingLeave} detail={`${leaveSummary.approved || 0} approved requests`} icon={CalendarDays} tone="amber" />
        <StatCard label="People health" value={`${peopleHealth}%`} detail="Active workforce ratio" icon={CheckCircle2} tone="emerald" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Card>
          <div className="flex items-center justify-between">
            <div><p className="text-xs font-bold uppercase tracking-wider text-cyan-700">Infographic</p><h2 className="mt-1 text-xl font-bold text-slate-950">Organization pulse</h2></div>
            <Link to="/org-chart" className="flex items-center gap-1 text-sm font-semibold text-cyan-700 hover:text-cyan-900">View structure <ArrowRight size={15} /></Link>
          </div>
          <div className="mt-6 grid gap-6 md:grid-cols-[auto_1fr] md:items-center">
            <ProgressRing value={peopleHealth} label="Active workforce" />
            <div className="space-y-4">
              {[
                ['Active employees', activeEmployees, employees.length || 1, 'bg-cyan-500'],
                ['Pending leave', pendingLeave, Math.max(employees.length, 1), 'bg-amber-500'],
                ['Open tasks', pendingTasks, Math.max(tasks.length, 1), 'bg-violet-500'],
                ['Compliance items', complianceCount, Math.max((summary?.documents || 0) + complianceCount, 1), 'bg-rose-500'],
              ].map(([label, value, total, color]) => (
                <div key={label}>
                  <div className="mb-1 flex justify-between text-xs"><span className="font-medium text-slate-600">{label}</span><span className="font-bold text-slate-900">{value}</span></div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, Math.max(4, (value / total) * 100))}%` }} /></div>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between"><div><p className="text-xs font-bold uppercase tracking-wider text-violet-700">People today</p><h2 className="mt-1 text-xl font-bold">Recent hires</h2></div><Link to="/employees"><Button variant="ghost" size="sm">Directory <ArrowRight size={15} /></Button></Link></div>
          <div className="mt-5 space-y-3">
            {recentHires.length === 0 ? <EmptyState title="No employee records yet" description="New team members will appear here." /> : recentHires.map((employee) => (
              <div key={employee.id} className="flex items-center justify-between gap-3 rounded-2xl bg-slate-50 p-3">
                <div className="flex min-w-0 items-center gap-3"><Avatar name={employee.full_name} size="sm" /><div className="min-w-0"><p className="truncate text-sm font-semibold">{employee.full_name}</p><p className="truncate text-xs text-slate-500">{employee.job_title || 'Role not assigned'}</p></div></div>
                <Badge tone="blue">{formatDate(employee.hire_date)}</Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <div className="flex items-center justify-between"><div><p className="text-xs font-bold uppercase tracking-wider text-amber-700">Team calendar</p><h2 className="mt-1 text-xl font-bold">Upcoming time off</h2></div><Link to="/leave"><Button variant="ghost" size="sm">Open calendar <ArrowRight size={15} /></Button></Link></div>
          <div className="mt-5">
            {approvedUpcoming.length === 0 ? <EmptyState title="No approved leave coming up" description="Approved time-off requests will create a team availability timeline." /> : (
              <div className="space-y-3">{approvedUpcoming.map((request, index) => {
                const employee = employees.find((item) => item.id === request.employee_id);
                return <div key={request.id} className="grid grid-cols-[42px_1fr_auto] items-center gap-3 rounded-2xl border border-slate-100 p-3"><span className="grid h-10 w-10 place-items-center rounded-2xl bg-amber-50 text-sm font-bold text-amber-700">{index + 1}</span><div><p className="text-sm font-semibold">{employee?.full_name || 'Employee'}</p><p className="text-xs text-slate-500">{formatDate(request.start_date)} – {formatDate(request.end_date)}</p></div><Badge tone="green">{request.total_days} days</Badge></div>;
              })}</div>
            )}
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-2xl bg-rose-50 text-rose-700"><FileWarning size={19} /></span><div><p className="text-xs font-bold uppercase tracking-wider text-rose-700">Compliance</p><h2 className="font-bold">Attention needed</h2></div></div>
          <div className="mt-5 space-y-4">
            <div className="rounded-2xl bg-rose-50 p-4"><p className="text-2xl font-bold text-rose-700">{alerts.expiring_documents?.length || 0}</p><p className="text-sm text-rose-800">Documents expiring within 30 days</p></div>
            <div className="rounded-2xl bg-amber-50 p-4"><p className="text-2xl font-bold text-amber-700">{alerts.employees_missing_contracts?.length || 0}</p><p className="text-sm text-amber-800">People missing employment contracts</p></div>
            <Link to="/documents" className="flex items-center gap-2 text-sm font-semibold text-cyan-700">Review document library <ArrowRight size={15} /></Link>
          </div>
        </Card>
      </div>

      <Card>
        <div className="flex items-center justify-between"><div><p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Action center</p><h2 className="mt-1 text-xl font-bold">Quick actions</h2></div><Network className="text-slate-300" /></div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {quickActions.map(({ to, label, icon: Icon, tone }) => <Link key={label} to={to} className="group flex items-center gap-3 rounded-2xl border border-slate-100 p-4 transition hover:-translate-y-0.5 hover:border-cyan-200 hover:shadow-lg"><span className={`grid h-10 w-10 place-items-center rounded-2xl ${tone}`}><Icon size={18} /></span><span className="text-sm font-semibold text-slate-800">{label}</span><ArrowRight className="ml-auto text-slate-300 transition group-hover:text-cyan-600" size={16} /></Link>)}
          {quickActions.length === 0 && <p className="text-sm text-slate-500">No actions are available for this role.</p>}
        </div>
      </Card>
    </div>
  );
}
