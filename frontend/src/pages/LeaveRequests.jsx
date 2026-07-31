import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Hourglass,
  Plus,
  Settings2,
  Umbrella,
} from 'lucide-react';

import { employeeApi } from '../api/employeeApi';
import { leaveApi } from '../api/leaveApi';
import LeaveLedgerPanel from '../components/leave/LeaveLedgerPanel.jsx';
import LeaveRequestForm from '../components/leave/LeaveRequestForm.jsx';
import LeaveSetupPanel from '../components/leave/LeaveSetupPanel.jsx';
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
import {
  annualLeaveMetrics,
  leaveEntitlementPresentation,
} from '../utils/leaveBalances.js';

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

function formatDate(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('en', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(`${value}T00:00:00`));
}

export default function LeaveRequests() {
  const { hasPermission } = usePermissions();
  const canApprove = hasPermission('leave:approve');
  const canAdjust = hasPermission('leave:adjust');

  const [requests, setRequests] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [types, setTypes] = useState([]);
  const [balances, setBalances] = useState([]);
  const [ledgerEntries, setLedgerEntries] = useState([]);
  const [setup, setSetup] = useState(null);
  const [requestOpen, setRequestOpen] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [month, setMonth] = useState(
    () => new Date(
      new Date().getFullYear(),
      new Date().getMonth(),
      1,
    ),
  );
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const [
        requestResponse,
        employeeResponse,
        typeResponse,
        balanceResponse,
        setupResponse,
        ledgerResponse,
      ] = await Promise.all([
        leaveApi.requests(),
        employeeApi.list({ per_page: 100 }),
        leaveApi.types(),
        leaveApi.balances(),
        leaveApi.setup(),
        leaveApi.ledger({ per_page: 50 }),
      ]);
      setRequests(requestResponse.data.items || []);
      setEmployees(employeeResponse.data.items || []);
      setTypes(typeResponse.data.items || []);
      setBalances(balanceResponse.data.items || []);
      setSetup(setupResponse.data);
      setLedgerEntries(ledgerResponse.data.items || []);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to load time off',
      );
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const employeeNames = useMemo(
    () => Object.fromEntries(
      employees.map((item) => [item.id, item.full_name]),
    ),
    [employees],
  );
  const typeNames = useMemo(
    () => Object.fromEntries(
      types.map((item) => [item.id, item.name]),
    ),
    [types],
  );

  const approvalQueue = requests.filter(
    (item) => item.can_decide,
  );
  const approved = requests.filter(
    (item) => item.status === 'approved',
  );
  const currentEmployeeId = setup?.current_employee?.id || '';
  const annualMetrics = annualLeaveMetrics(
    types,
    balances,
    currentEmployeeId,
  );
  const {
    personalBalances,
    available: annualAvailable,
    used: annualUsed,
    reserved: annualReserved,
    utilization,
  } = annualMetrics;

  const requestEmployees = setup?.can_submit_for_others
    ? employees
    : employees.filter(
      (employee) => (
        String(employee.id) === String(currentEmployeeId)
      ),
    );

  const firstDay = new Date(
    month.getFullYear(),
    month.getMonth(),
    1,
  );
  const gridStart = new Date(firstDay);
  gridStart.setDate(
    firstDay.getDate() - firstDay.getDay(),
  );
  const days = Array.from({ length: 42 }, (_, index) => {
    const value = new Date(gridStart);
    value.setDate(gridStart.getDate() + index);
    return value;
  });
  const monthLabel = new Intl.DateTimeFormat('en', {
    month: 'long',
    year: 'numeric',
  }).format(month);

  const requestsForDay = (date) => {
    const day = isoDate(date);
    return approved.filter(
      (item) => (
        item.start_date <= day
        && item.end_date >= day
      ),
    );
  };

  const runAction = async (action, successMessage) => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await action();
      setMessage(successMessage);
      await load();
      return true;
    } catch (err) {
      setError(
        err.error?.message
        || 'The time-off action could not be completed',
      );
      return false;
    } finally {
      setSaving(false);
    }
  };

  const submit = async (payload) => {
    const completed = await runAction(
      () => leaveApi.submit(payload),
      'Time-off request submitted.',
    );
    if (completed) setRequestOpen(false);
  };

  const decide = async (id, decision) => {
    await runAction(
      () => (
        decision === 'approved'
          ? leaveApi.approve(id)
          : leaveApi.reject(id)
      ),
      `Leave request ${decision}.`,
    );
  };

  const saveGovernance = async (payload) => {
    const completed = await runAction(
      () => leaveApi.saveGovernance(payload),
      'Approval governance updated.',
    );
    if (completed) setSetupOpen(false);
  };

  const applyPack = async (payload) => {
    await runAction(
      () => leaveApi.applyStandardPack(payload),
      'Standard leave policy pack applied.',
    );
  };

  const initializeBalances = async (payload) => {
    await runAction(
      () => leaveApi.initializeBalances(payload),
      'Opening balances initialized.',
    );
  };

  const runAccruals = async (payload = {}) => runAction(
    () => leaveApi.runAccruals(payload),
    'Scheduled leave allocations processed.',
  );

  const adjustBalance = async (balanceId, payload) => runAction(
    () => leaveApi.adjustBalance(balanceId, payload),
    'Leave balance adjustment posted.',
  );

  const cancelRequest = async (id) => runAction(
    () => leaveApi.cancel(id),
    'Leave request cancelled and balance restored.',
  );

  const openRequest = () => {
    setError('');

    if (!setup?.ready_to_request) {
      if (setup?.can_configure) {
        setSetupOpen(true);
      } else {
        setError(
          'Time-off requests are not available yet. '
          + 'Contact HR or your organization administrator.',
        );
      }
      return;
    }
    setRequestOpen(true);
  };

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Time"
        title="Time off"
        description="Policy setup, balances, team availability and governed approvals in one workspace."
        actions={(
          <div className="flex flex-wrap gap-2">
            {setup?.can_configure && (
              <Button
                variant="secondary"
                onClick={() => setSetupOpen(true)}
              >
                <Settings2 size={17} />
                Configure time off
              </Button>
            )}
            <Button
              variant="accent"
              onClick={openRequest}
              disabled={!setup}
            >
              <Plus size={17} />
              Request time off
            </Button>
          </div>
        )}
      />

      {error && <Alert type="error">{error}</Alert>}
      {message && <Alert type="success">{message}</Alert>}

      {setup && !setup.ready_to_request && setup.can_configure && (
        <Card className="border-amber-200 bg-amber-50/80">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-amber-700">
                Setup required
              </p>
              <h2 className="mt-1 text-xl font-bold text-amber-950">
                Complete time-off setup before requesting leave
              </h2>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {setup.missing_requirements.map((item) => (
                  <div
                    key={item.code}
                    className="rounded-xl bg-white/80 px-4 py-3"
                  >
                    <p className="font-semibold text-slate-900">
                      {item.title}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {item.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
            {setup.can_configure && (
              <Button onClick={() => setSetupOpen(true)}>
                Complete setup
              </Button>
            )}
          </div>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Awaiting your decision"
          value={approvalQueue.length}
          detail={
            canApprove
              ? 'Requests assigned to you'
              : 'No approval responsibility'
          }
          icon={Clock3}
          tone="amber"
        />
        <StatCard
          label="Approved leave"
          value={approved.length}
          detail="Requests visible on the calendar"
          icon={CheckCircle2}
          tone="emerald"
        />
        <StatCard
          label="Annual leave available"
          value={`${annualAvailable.toFixed(1)} d`}
          detail={`${annualUsed.toFixed(1)} days used`}
          icon={Umbrella}
          tone="blue"
        />
        <StatCard
          label="Annual leave reserved"
          value={`${annualReserved.toFixed(1)} d`}
          detail="Held by pending annual-leave requests"
          icon={Hourglass}
          tone="amber"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-cyan-700">
                People’s time off
              </p>
              <h2 className="mt-1 text-xl font-bold">
                {monthLabel}
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setMonth(
                  new Date(
                    month.getFullYear(),
                    month.getMonth() - 1,
                    1,
                  ),
                )}
              >
                <ChevronLeft size={16} />
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setMonth(new Date())}
              >
                Today
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setMonth(
                  new Date(
                    month.getFullYear(),
                    month.getMonth() + 1,
                    1,
                  ),
                )}
              >
                <ChevronRight size={16} />
              </Button>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-7 gap-px overflow-hidden rounded-2xl bg-slate-200">
            {[
              'Sun',
              'Mon',
              'Tue',
              'Wed',
              'Thu',
              'Fri',
              'Sat',
            ].map((day) => (
              <div
                key={day}
                className="bg-slate-50 px-2 py-3 text-center text-xs font-bold uppercase tracking-wider text-slate-500"
              >
                {day}
              </div>
            ))}

            {days.map((date) => {
              const dayRequests = requestsForDay(date);
              const inMonth = date.getMonth() === month.getMonth();
              const isToday = isoDate(date) === isoDate(new Date());

              return (
                <div
                  key={date.toISOString()}
                  className={`min-h-24 bg-white p-2 ${inMonth ? '' : 'opacity-45'}`}
                >
                  <span
                    className={`grid h-7 w-7 place-items-center rounded-full text-xs font-semibold ${
                      isToday
                        ? 'bg-slate-950 text-white'
                        : 'text-slate-600'
                    }`}
                  >
                    {date.getDate()}
                  </span>
                  <div className="mt-2 space-y-1">
                    {dayRequests.slice(0, 2).map((item) => (
                      <div
                        key={item.id}
                        title={item.employee_name}
                        className="truncate rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-2 py-1 text-[10px] font-semibold text-white"
                      >
                        {item.employee_name}
                      </div>
                    ))}
                    {dayRequests.length > 2 && (
                      <p className="text-[10px] font-semibold text-slate-500">
                        +{dayRequests.length - 2} more
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <Card className="bg-gradient-to-br from-cyan-50 to-violet-50">
          <div className="text-center">
            <ProgressRing
              value={utilization}
              size={148}
              stroke={12}
              label="Annual leave utilization"
            />
          </div>
          <div className="mt-6 space-y-3">
            {types.slice(0, 8).map((type) => {
              const balance = personalBalances.find(
                (item) => item.leave_type_id === type.id,
              );
              const presentation = leaveEntitlementPresentation(
                type,
                balance,
              );

              return (
                <div
                  key={type.id}
                  className="flex items-center justify-between rounded-2xl bg-white/80 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      {type.name}
                    </p>
                    <p className="text-xs text-slate-500">
                      {presentation.detail}
                    </p>
                  </div>
                  <Badge tone="blue">
                    {presentation.value}
                  </Badge>
                </div>
              );
            })}
            {types.length === 0 && (
              <p className="text-center text-sm text-slate-500">
                Leave policies have not been configured.
              </p>
            )}
          </div>
        </Card>
      </div>

      <Card>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-amber-700">
              Requests
            </p>
            <h2 className="mt-1 text-xl font-bold">
              {approvalQueue.length
                ? 'Your approval queue'
                : 'Request history'}
            </h2>
          </div>
          <CalendarDays className="text-slate-300" />
        </div>

        <div className="mt-5 space-y-3">
          {requests.length === 0 ? (
            <EmptyState
              title="No leave requests"
              description="New requests appear here and flow into the calendar after approval."
            />
          ) : requests.slice(0, 16).map((item) => (
            <div
              key={item.id}
              className="flex flex-col gap-4 rounded-2xl border border-slate-100 p-4 lg:flex-row lg:items-center"
            >
              <Avatar
                name={
                  item.employee_name
                  || employeeNames[item.employee_id]
                  || 'Employee'
                }
                size="sm"
              />
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-slate-900">
                  {item.employee_name
                    || employeeNames[item.employee_id]
                    || 'Employee'}
                </p>
                <p className="text-xs text-slate-500">
                  {item.leave_type_name
                    || typeNames[item.leave_type_id]
                    || 'Leave'}
                  {' · '}
                  {formatDate(item.start_date)}
                  {' – '}
                  {formatDate(item.end_date)}
                </p>
                {item.required_approver_name && (
                  <p className="mt-1 text-xs text-slate-500">
                    Approver: {item.required_approver_name}
                  </p>
                )}
              </div>
              <Badge
                tone={
                  item.status === 'approved'
                    ? 'green'
                    : item.status === 'rejected'
                      ? 'red'
                      : 'amber'
                }
              >
                {item.status}
              </Badge>
              <span className="text-sm font-bold text-slate-700">
                {item.total_days} days
              </span>
              {item.can_decide && (
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="soft"
                    disabled={saving}
                    onClick={() => decide(item.id, 'approved')}
                  >
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={saving}
                    onClick={() => decide(item.id, 'rejected')}
                  >
                    Reject
                  </Button>
                </div>
              )}
              {item.can_cancel && (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={saving}
                  onClick={() => cancelRequest(item.id)}
                >
                  Cancel
                </Button>
              )}
            </div>
          ))}
        </div>
      </Card>

      <LeaveLedgerPanel
        entries={ledgerEntries}
        balances={balances}
        employees={employees}
        leaveTypes={types}
        canAdjust={canAdjust}
        onAdjust={adjustBalance}
        onRunAccruals={runAccruals}
        loading={saving}
      />

      <Modal
        title="Submit time-off request"
        open={requestOpen}
        onClose={() => setRequestOpen(false)}
      >
        {setup?.ready_to_request ? (
          <LeaveRequestForm
            employees={requestEmployees}
            leaveTypes={types}
            balances={balances}
            defaultEmployeeId={currentEmployeeId}
            onSubmit={submit}
            loading={saving}
          />
        ) : (
          <EmptyState
            title="Time-off setup incomplete"
            description="Complete the missing employee, policy, balance and approval prerequisites first."
          />
        )}
      </Modal>

      <Modal
        title="Configure time off"
        open={setupOpen}
        onClose={() => setSetupOpen(false)}
        size="xl"
      >
        {setup?.can_configure ? (
          <LeaveSetupPanel
            setup={setup}
            onSaveGovernance={saveGovernance}
            onApplyPack={applyPack}
            onInitializeBalances={initializeBalances}
            onRunAccruals={runAccruals}
            loading={saving}
          />
        ) : (
          <EmptyState
            title="Administrator action required"
            description="Ask an organization owner, HR consultant or client administrator to complete time-off setup."
          />
        )}
      </Modal>
    </div>
  );
}
