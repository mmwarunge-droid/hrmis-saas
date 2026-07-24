import { useEffect, useMemo, useState } from 'react';
import { CalendarDays, CheckCircle2, ChevronLeft, ChevronRight, Clock3, Plus, Umbrella } from 'lucide-react';
import { employeeApi } from '../api/employeeApi';
import { leaveApi } from '../api/leaveApi';
import LeaveRequestForm from '../components/leave/LeaveRequestForm.jsx';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import Modal from '../components/ui/Modal.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import ProgressRing from '../components/ui/ProgressRing.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import usePermissions from '../hooks/usePermissions.js';

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

function formatDate(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T00:00:00`));
}

export default function LeaveRequests() {
  const [requests, setRequests] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [types, setTypes] = useState([]);
  const [balances, setBalances] = useState([]);
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [error, setError] = useState('');
  const { hasPermission } = usePermissions();
  const canApprove = hasPermission('leave:approve');

  const load = async () => {
    try {
      const [requestResponse, employeeResponse, typeResponse, balanceResponse] = await Promise.all([
        leaveApi.requests(),
        employeeApi.list(),
        leaveApi.types(),
        leaveApi.balances(),
      ]);
      setRequests(requestResponse.data.items || []);
      setEmployees(employeeResponse.data.items || []);
      setTypes(typeResponse.data.items || []);
      setBalances(balanceResponse.data.items || []);
    } catch (err) {
      setError(err.error?.message || 'Unable to load time off');
    }
  };
  useEffect(() => {
    let cancelled = false;

    Promise.all([
      leaveApi.requests(),
      employeeApi.list(),
      leaveApi.types(),
      leaveApi.balances(),
    ])
      .then(([requestResponse, employeeResponse, typeResponse, balanceResponse]) => {
        if (cancelled) return;

        setRequests(requestResponse.data.items || []);
        setEmployees(employeeResponse.data.items || []);
        setTypes(typeResponse.data.items || []);
        setBalances(balanceResponse.data.items || []);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.error?.message || 'Unable to load time off');
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const employeeNames = useMemo(() => Object.fromEntries(employees.map((item) => [item.id, item.full_name])), [employees]);
  const typeNames = useMemo(() => Object.fromEntries(types.map((item) => [item.id, item.name])), [types]);
  const pending = requests.filter((request) => request.status === 'pending');
  const approved = requests.filter((request) => request.status === 'approved');
  const totalBalance = balances.reduce((sum, balance) => sum + Number(balance.balance_days || 0), 0);
  const totalUsed = balances.reduce((sum, balance) => sum + Number(balance.used_days || 0), 0);
  const utilization = totalBalance + totalUsed > 0 ? Math.round((totalUsed / (totalBalance + totalUsed)) * 100) : 0;

  const firstDay = new Date(month.getFullYear(), month.getMonth(), 1);
  const gridStart = new Date(firstDay);
  gridStart.setDate(firstDay.getDate() - firstDay.getDay());
  const days = Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart);
    date.setDate(gridStart.getDate() + index);
    return date;
  });
  const monthLabel = new Intl.DateTimeFormat('en', { month: 'long', year: 'numeric' }).format(month);

  const requestsForDay = (date) => {
    const day = isoDate(date);
    return approved.filter((request) => request.start_date <= day && request.end_date >= day);
  };

  const submit = async (payload) => {
    try {
      await leaveApi.submit(payload);
      setOpen(false);
      await load();
    } catch (err) {
      setError(err.error?.message || 'Leave request failed');
    }
  };

  const decide = async (id, decision) => {
    try {
      if (decision === 'approved') await leaveApi.approve(id);
      else await leaveApi.reject(id);
      await load();
    } catch (err) {
      setError(err.error?.message || 'Leave decision failed');
    }
  };

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Time"
        title="Time off"
        description="Balance visibility, team availability and approval workflows in a single calendar-led workspace."
        actions={<Button variant="accent" onClick={() => setOpen(true)}><Plus size={17} /> Request time off</Button>}
      />
      {error && <Alert type="error">{error}</Alert>}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Pending requests" value={pending.length} detail={canApprove ? 'Waiting for approval' : 'Awaiting manager action'} icon={Clock3} tone="amber" />
        <StatCard label="Approved leave" value={approved.length} detail="Requests visible on the team calendar" icon={CheckCircle2} tone="emerald" />
        <StatCard label="Available balance" value={`${totalBalance.toFixed(1)} d`} detail={`${totalUsed.toFixed(1)} days used`} icon={Umbrella} tone="blue" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><p className="text-xs font-bold uppercase tracking-wider text-cyan-700">People’s time off</p><h2 className="mt-1 text-xl font-bold">{monthLabel}</h2></div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}><ChevronLeft size={16} /></Button>
              <Button variant="secondary" size="sm" onClick={() => setMonth(new Date())}>Today</Button>
              <Button variant="secondary" size="sm" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}><ChevronRight size={16} /></Button>
            </div>
          </div>
          <div className="mt-6 grid grid-cols-7 gap-px overflow-hidden rounded-2xl bg-slate-200">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => <div key={day} className="bg-slate-50 px-2 py-3 text-center text-xs font-bold uppercase tracking-wider text-slate-500">{day}</div>)}
            {days.map((date) => {
              const dayRequests = requestsForDay(date);
              const inMonth = date.getMonth() === month.getMonth();
              const isToday = isoDate(date) === isoDate(new Date());
              return (
                <div key={date.toISOString()} className={`min-h-24 bg-white p-2 ${inMonth ? '' : 'opacity-45'}`}>
                  <span className={`grid h-7 w-7 place-items-center rounded-full text-xs font-semibold ${isToday ? 'bg-slate-950 text-white' : 'text-slate-600'}`}>{date.getDate()}</span>
                  <div className="mt-2 space-y-1">
                    {dayRequests.slice(0, 2).map((request) => <div key={request.id} title={employeeNames[request.employee_id]} className="truncate rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-2 py-1 text-[10px] font-semibold text-white">{employeeNames[request.employee_id] || 'Employee'}</div>)}
                    {dayRequests.length > 2 && <p className="text-[10px] font-semibold text-slate-500">+{dayRequests.length - 2} more</p>}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <Card className="bg-gradient-to-br from-cyan-50 to-violet-50">
          <div className="text-center"><ProgressRing value={utilization} size={148} stroke={12} label="Leave utilization" /></div>
          <div className="mt-6 space-y-3">
            {types.slice(0, 5).map((type) => {
              const typeBalances = balances.filter((balance) => balance.leave_type_id === type.id);
              const available = typeBalances.reduce((sum, item) => sum + Number(item.balance_days || 0), 0);
              return <div key={type.id} className="flex items-center justify-between rounded-2xl bg-white/80 px-4 py-3"><div><p className="text-sm font-semibold text-slate-800">{type.name}</p><p className="text-xs text-slate-500">{type.annual_entitlement_days} days annual entitlement</p></div><Badge tone="blue">{available.toFixed(1)} d</Badge></div>;
            })}
            {types.length === 0 && <p className="text-center text-sm text-slate-500">Leave policies have not been configured.</p>}
          </div>
        </Card>
      </div>

      <Card>
        <div className="flex items-center justify-between"><div><p className="text-xs font-bold uppercase tracking-wider text-amber-700">Requests</p><h2 className="mt-1 text-xl font-bold">{canApprove ? 'Approval queue' : 'My requests'}</h2></div><CalendarDays className="text-slate-300" /></div>
        <div className="mt-5 space-y-3">
          {(canApprove ? pending : requests).length === 0 ? <EmptyState title="No leave requests" description="New requests will appear here and flow into the shared calendar after approval." /> : (canApprove ? pending : requests).slice(0, 12).map((request) => (
            <div key={request.id} className="flex flex-col gap-4 rounded-2xl border border-slate-100 p-4 lg:flex-row lg:items-center">
              <Avatar name={employeeNames[request.employee_id] || 'Employee'} size="sm" />
              <div className="min-w-0 flex-1"><p className="font-semibold text-slate-900">{employeeNames[request.employee_id] || 'Employee'}</p><p className="text-xs text-slate-500">{typeNames[request.leave_type_id] || 'Leave'} · {formatDate(request.start_date)} – {formatDate(request.end_date)}</p></div>
              <Badge tone={request.status === 'approved' ? 'green' : request.status === 'rejected' ? 'red' : 'amber'}>{request.status}</Badge>
              <span className="text-sm font-bold text-slate-700">{request.total_days} days</span>
              {canApprove && request.status === 'pending' && <div className="flex gap-2"><Button size="sm" variant="soft" onClick={() => decide(request.id, 'approved')}>Approve</Button><Button size="sm" variant="ghost" onClick={() => decide(request.id, 'rejected')}>Reject</Button></div>}
            </div>
          ))}
        </div>
      </Card>

      <Modal title="Submit time-off request" open={open} onClose={() => setOpen(false)}>
        {employees.length && types.length ? <LeaveRequestForm employees={employees} leaveTypes={types} onSubmit={submit} /> : <EmptyState title="Time-off setup incomplete" description="An employee profile and at least one leave policy are required before a request can be submitted." />}
      </Modal>
    </div>
  );
}
