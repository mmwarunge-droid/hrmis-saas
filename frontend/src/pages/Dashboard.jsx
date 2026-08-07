import { useEffect, useState } from 'react';
import {
  ArrowRight,
  BriefcaseBusiness,
  CalendarDays,
  CheckCircle2,
  FileText,
  FileWarning,
  Network,
  Sparkles,
  Target,
  UserPlus,
  UsersRound,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { dashboardApi } from '../api/dashboardApi';
import { onboardingApi } from '../api/onboardingApi';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import Skeleton from '../components/ui/Skeleton.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import useAuth from '../hooks/useAuth.js';
import usePermissions from '../hooks/usePermissions.js';

const settleData = (result, fallback) => result.status === 'fulfilled' ? result.value.data : fallback;

function dateFromValue(value) {
  return new Date(`${value}T00:00:00`);
}

function formatDate(value) {
  if (!value) return 'No date';
  return new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short' }).format(dateFromValue(value));
}

function formatLongDate(value) {
  return new Intl.DateTimeFormat('en', { weekday: 'long', day: 'numeric', month: 'long' }).format(value);
}

function dayPart(value) {
  const hour = value.getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

export default function Dashboard() {
  const { user } = useAuth();
  const { hasPermission } = usePermissions();
  const [today] = useState(() => new Date());
  const [summary, setSummary] = useState(null);
  const [alerts, setAlerts] = useState({ expiring_documents: [], employees_missing_contracts: [] });
  const [leaveSummary, setLeaveSummary] = useState({});
  const [tasks, setTasks] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const requests = [
      dashboardApi.summary(),
      dashboardApi.complianceAlerts(),
      dashboardApi.leaveSummary(),
      onboardingApi.myTasks(),
    ];
    Promise.allSettled(requests).then((results) => {
      const [summaryResult, alertsResult, leaveSummaryResult, tasksResult] = results;
      setSummary(settleData(summaryResult, null));
      setAlerts(settleData(alertsResult, { expiring_documents: [], employees_missing_contracts: [] }));
      setLeaveSummary(settleData(leaveSummaryResult, { by_status: {} }).by_status || {});
      setTasks(settleData(tasksResult, { items: [] }).items || []);
      if (summaryResult.status === 'rejected') {
        setError(summaryResult.reason?.error?.message || 'Some dashboard data could not be loaded.');
      }
      setLoading(false);
    });
  }, []);

  const activeEmployees = summary?.active_employees || 0;
  const employeeTotal = summary?.employees || 0;
  const peopleHealth = summary?.people_health_percent || 0;
  const pendingTasks = tasks.filter((task) => !['completed', 'waived'].includes(task.status)).length;
  const pendingLeave = leaveSummary.pending || summary?.pending_leave_requests || 0;
  const approvedUpcoming = summary?.upcoming_leave || [];
  const recentHires = summary?.recent_hires || [];
  const complianceCount = (alerts.expiring_documents?.length || 0) + (alerts.employees_missing_contracts?.length || 0);
  const goalSummary = summary?.goals || { average_progress: 0, at_risk: 0, off_track: 0, overdue: 0 };
  const goalAttention = (goalSummary.at_risk || 0) + (goalSummary.off_track || 0);

  const quickActions = [
    hasPermission('leave:create') && { to: '/leave', label: 'Request time off', detail: 'Submit a new request', icon: CalendarDays },
    hasPermission('employee:create') && { to: '/employees', label: 'Add a person', detail: 'Create an employee record', icon: UserPlus },
    hasPermission('document:upload') && { to: '/documents', label: 'Upload a file', detail: 'Add a policy or document', icon: FileText },
    hasPermission('onboarding:assign') && { to: '/tasks', label: 'Review tasks', detail: 'Open assigned work', icon: CheckCircle2 },
    hasPermission('goal:read') && { to: '/goals', label: 'Review goals', detail: 'Check performance progress', icon: Target },
  ].filter(Boolean);

  const PrimaryActionIcon = quickActions[0]?.icon;

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex justify-between"><div className="space-y-2"><Skeleton className="h-7 w-72" /><Skeleton className="h-4 w-96" /></div><Skeleton className="h-10 w-36" /></div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>
        <div className="grid gap-5 xl:grid-cols-[1.6fr_1fr]"><Skeleton className="h-96" /><Skeleton className="h-96" /></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Home"
        title={`${dayPart(today)}, ${user?.first_name || 'there'}`}
        description={`${formatLongDate(today)}. Here is what is happening across your organization.`}
        actions={quickActions[0] && (
          <Button as={Link} to={quickActions[0].to}>{PrimaryActionIcon && <PrimaryActionIcon size={16} />}{quickActions[0].label}</Button>
        )}
      />

      {error && <Alert type="warning">{error}</Alert>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Total people" value={employeeTotal} detail={`${activeEmployees} currently active`} icon={UsersRound} tone="blue" />
        <StatCard label="Open tasks" value={pendingTasks} detail={`${tasks.length - pendingTasks} completed or waived`} icon={CheckCircle2} tone="violet" />
        <StatCard label="Pending time off" value={pendingLeave} detail={`${leaveSummary.approved || 0} approved requests`} icon={CalendarDays} tone="amber" />
        <StatCard label="Workforce active" value={`${peopleHealth}%`} detail={`${summary?.inactive_employees || 0} not active`} icon={Network} tone="emerald" />
        <StatCard label="Goal progress" value={`${goalSummary.average_progress || 0}%`} detail={`${goalAttention} need attention`} icon={Target} tone="blue" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.75fr)]">
        <div className="space-y-5">
          <Card>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-blue-700">Team calendar</p>
                <h2 className="mt-1 text-lg font-bold text-slate-950">Who’s out</h2>
                <p className="mt-1 text-sm text-slate-500">Approved time off coming up across your team.</p>
              </div>
              <Link to="/leave" className="inline-flex items-center gap-1 text-sm font-semibold text-blue-700 hover:text-blue-900">View calendar <ArrowRight size={15} /></Link>
            </div>

            <div className="mt-5">
              {approvedUpcoming.length === 0 ? (
                <EmptyState title="No upcoming time off" description="Approved requests will appear here so the team can plan ahead." icon={CalendarDays} />
              ) : (
                <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                  {approvedUpcoming.map((request) => (
                    <div key={request.id} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50">
                      <Avatar
                        name={request.employee_name || 'Employee'}
                        size="sm"
                        src={request.employee_profile_photo_url}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-slate-900">{request.employee_name || 'Employee'}</p>
                        <p className="truncate text-xs text-slate-500">{formatDate(request.start_date)} – {formatDate(request.end_date)}</p>
                      </div>
                      <Badge tone="blue">{request.total_days} {request.total_days === 1 ? 'day' : 'days'}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <Card>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-blue-700">People</p>
                <h2 className="mt-1 text-lg font-bold text-slate-950">Recently joined</h2>
              </div>
              <Link to="/employees" className="inline-flex items-center gap-1 text-sm font-semibold text-blue-700 hover:text-blue-900">Open directory <ArrowRight size={15} /></Link>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {recentHires.length === 0 ? (
                <div className="sm:col-span-2"><EmptyState title="No employee records yet" description="New team members will appear here." icon={UsersRound} /></div>
              ) : recentHires.map((employee) => (
                <Link key={employee.id} to={`/employees/${employee.id}`} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3 transition hover:border-blue-200 hover:bg-blue-50/40">
                  <Avatar name={employee.full_name} size="md" src={employee.profile_photo_url} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-slate-900">{employee.full_name}</p>
                    <p className="truncate text-xs text-slate-500">{employee.job_title || 'Role not assigned'}</p>
                    <p className="mt-1 text-[11px] font-medium text-blue-700">Joined {formatDate(employee.hire_date)}</p>
                  </div>
                </Link>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          <Card>
            <div className="flex items-center gap-3">
              <span className="grid h-9 w-9 place-items-center rounded-lg border border-amber-100 bg-amber-50 text-amber-700"><Sparkles size={17} /></span>
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-amber-700">My work</p>
                <h2 className="text-base font-bold text-slate-950">Needs your attention</h2>
              </div>
            </div>
            <div className="mt-4 divide-y divide-slate-100 rounded-lg border border-slate-200">
              {[
                { to: '/leave', label: 'Time-off approvals', value: pendingLeave, icon: CalendarDays },
                { to: '/tasks', label: 'Open onboarding tasks', value: pendingTasks, icon: CheckCircle2 },
                { to: '/documents', label: 'Compliance items', value: complianceCount, icon: FileWarning },
                { to: '/goals', label: 'Goals needing attention', value: goalAttention, icon: Target },
              ].map(({ to, label, value, icon: Icon }) => (
                <Link key={label} to={to} className="flex items-center gap-3 px-3.5 py-3 hover:bg-slate-50">
                  <Icon size={17} className="text-slate-500" />
                  <span className="flex-1 text-sm font-medium text-slate-700">{label}</span>
                  <span className={`grid min-w-7 place-items-center rounded-full px-2 py-0.5 text-xs font-bold ${value ? 'bg-blue-700 text-white' : 'bg-slate-100 text-slate-500'}`}>{value}</span>
                </Link>
              ))}
            </div>
          </Card>

          <Card>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-blue-700">Quick access</p>
                <h2 className="mt-1 text-base font-bold text-slate-950">Common actions</h2>
              </div>
              <BriefcaseBusiness className="text-slate-300" size={20} />
            </div>
            <div className="mt-4 space-y-1">
              {quickActions.map(({ to, label, detail, icon: Icon }) => (
                <Link key={label} to={to} className="group flex items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-blue-50">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600 group-hover:border-blue-200 group-hover:text-blue-700"><Icon size={17} /></span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-slate-800">{label}</span>
                    <span className="block truncate text-xs text-slate-500">{detail}</span>
                  </span>
                  <ArrowRight size={14} className="text-slate-300 group-hover:text-blue-600" />
                </Link>
              ))}
              {quickActions.length === 0 && <p className="py-4 text-sm text-slate-500">No actions are available for this role.</p>}
            </div>
          </Card>

          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-red-700">Compliance</p>
                <h2 className="mt-1 text-base font-bold text-slate-950">Document health</h2>
              </div>
              <FileWarning className="text-red-500" size={19} />
            </div>
            <dl className="mt-4 space-y-3">
              <div className="flex items-center justify-between text-sm"><dt className="text-slate-600">Expiring within 30 days</dt><dd className="font-bold text-slate-950">{alerts.expiring_documents?.length || 0}</dd></div>
              <div className="flex items-center justify-between text-sm"><dt className="text-slate-600">Missing contracts</dt><dd className="font-bold text-slate-950">{alerts.employees_missing_contracts?.length || 0}</dd></div>
            </dl>
            <Link to="/documents" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-blue-700 hover:text-blue-900">Review files <ArrowRight size={15} /></Link>
          </Card>
        </div>
      </div>
    </div>
  );
}
