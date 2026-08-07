import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  CircleGauge,
  Plus,
  Search,
  Target,
  TrendingUp,
  X,
} from 'lucide-react';
import { departmentApi } from '../api/departmentApi.js';
import { employeeApi } from '../api/employeeApi.js';
import { goalApi } from '../api/goalApi.js';
import GoalCheckInForm from '../components/goals/GoalCheckInForm.jsx';
import GoalForm from '../components/goals/GoalForm.jsx';
import Alert from '../components/ui/Alert.jsx';
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
import usePermissions from '../hooks/usePermissions.js';

function badgeTone(health) {
  return {
    on_track: 'green',
    at_risk: 'amber',
    off_track: 'red',
    completed: 'blue',
  }[health] || 'slate';
}

function formatDate(value) {
  if (!value) return 'Not set';
  return new Intl.DateTimeFormat('en', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(`${value}T00:00:00`));
}

function ownerName(goal) {
  if (goal.owner_type === 'organization') return 'Organization';
  return goal.employee_name || goal.department_name || 'Unassigned';
}

export default function Goals() {
  const { hasPermission } = usePermissions();
  const canManage = hasPermission('goal:manage');
  const canCheckIn = hasPermission('goal:checkin');
  const [goals, setGoals] = useState([]);
  const [summary, setSummary] = useState({
    total: 0,
    active: 0,
    average_progress: 0,
    on_track: 0,
    at_risk: 0,
    off_track: 0,
    overdue: 0,
    completed: 0,
    due_soon: 0,
  });
  const [meta, setMeta] = useState({ page: 1, per_page: 15, total: 0, pages: 1 });
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [health, setHealth] = useState('');
  const [ownerType, setOwnerType] = useState('');
  const [sort, setSort] = useState({ key: 'due_date', direction: 'asc' });
  const [employees, setEmployees] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedGoal, setSelectedGoal] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadReferenceData = useCallback(async () => {
    if (!canManage) return;
    const results = await Promise.allSettled([
      employeeApi.options(),
      departmentApi.list(),
    ]);
    if (results[0].status === 'fulfilled') {
      setEmployees(results[0].value.data.items || []);
    }
    if (results[1].status === 'fulfilled') {
      setDepartments(results[1].value.data.items || []);
    }
  }, [canManage]);

  const loadSummary = useCallback(async () => {
    try {
      const response = await goalApi.summary();
      setSummary(response.data);
    } catch (err) {
      setError(err.error?.message || 'Unable to load goal totals');
    }
  }, []);

  const loadGoals = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await goalApi.list({
        page,
        per_page: 15,
        q: query || undefined,
        status: status || undefined,
        health: health || undefined,
        owner_type: ownerType || undefined,
        sort: sort.key,
        direction: sort.direction,
      });
      setGoals(response.data.items || []);
      setMeta(response.data.meta || { page, per_page: 15, total: 0, pages: 1 });
    } catch (err) {
      setError(err.error?.message || 'Unable to load goals');
    } finally {
      setLoading(false);
    }
  }, [health, ownerType, page, query, sort, status]);

  useEffect(() => { loadReferenceData(); }, [loadReferenceData]);
  useEffect(() => { loadSummary(); }, [loadSummary]);
  useEffect(() => { loadGoals(); }, [loadGoals]);

  const refresh = async () => Promise.all([loadGoals(), loadSummary()]);

  const createGoal = async (payload) => {
    setSaving(true);
    setError('');
    try {
      await goalApi.create(payload);
      setCreateOpen(false);
      setSuccess('Goal created and added to the performance workspace.');
      await refresh();
    } catch (err) {
      setError(err.error?.message || 'Goal creation failed');
    } finally {
      setSaving(false);
    }
  };

  const saveCheckIn = async (payload) => {
    if (!selectedGoal) return;
    setSaving(true);
    setError('');
    try {
      await goalApi.checkIn(selectedGoal.id, payload);
      setSelectedGoal(null);
      setSuccess('Goal progress updated.');
      await refresh();
    } catch (err) {
      setError(err.error?.message || 'Goal check-in failed');
    } finally {
      setSaving(false);
    }
  };

  const resetFilters = () => {
    setQuery('');
    setStatus('');
    setHealth('');
    setOwnerType('');
    setPage(1);
  };

  const hasFilters = Boolean(query || status || health || ownerType);
  const attention = summary.at_risk + summary.off_track;
  const columns = useMemo(() => [
    {
      key: 'title',
      label: 'Goal',
      sortable: true,
      render: (goal) => (
        <div className="min-w-[240px]">
          <p className="font-semibold text-slate-900">{goal.title}</p>
          <p className="mt-1 text-xs capitalize text-slate-500">
            {goal.owner_type} · {ownerName(goal)}
          </p>
        </div>
      ),
    },
    {
      key: 'progress',
      label: 'Progress',
      sortable: true,
      render: (goal) => (
        <div className="min-w-[150px]">
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="font-semibold text-slate-700">{Math.round(goal.progress_percent)}%</span>
            <span className="text-slate-500">{goal.current_value}/{goal.target_value} {goal.unit}</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-blue-600 transition-all"
              style={{ width: `${Math.min(100, Math.max(0, goal.progress_percent))}%` }}
            />
          </div>
        </div>
      ),
    },
    {
      key: 'health',
      label: 'Health',
      sortable: true,
      render: (goal) => (
        <Badge tone={badgeTone(goal.health)}>{goal.health.replaceAll('_', ' ')}</Badge>
      ),
    },
    {
      key: 'due_date',
      label: 'Due',
      sortable: true,
      render: (goal) => formatDate(goal.due_date),
    },
    {
      key: 'status',
      label: 'Status',
      render: (goal) => <Badge tone={goal.status === 'completed' ? 'green' : 'slate'}>{goal.status}</Badge>,
    },
    ...(canCheckIn ? [{
      key: 'actions',
      label: '',
      cellClassName: 'w-28 text-right',
      render: (goal) => (
        <Button
          type="button"
          size="xs"
          variant="secondary"
          disabled={['completed', 'cancelled'].includes(goal.status)}
          onClick={() => setSelectedGoal(goal)}
          aria-label={`Check in ${goal.title}`}
        >
          Check in
        </Button>
      ),
    }] : []),
  ], [canCheckIn]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Performance"
        title="Goals & KPIs"
        description="Align organization outcomes, team priorities, and individual progress in one measurable workspace."
        actions={canManage && (
          <Button type="button" onClick={() => setCreateOpen(true)}>
            <Plus size={16} /> Create goal
          </Button>
        )}
      />

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active goals" value={summary.active} detail={`${summary.total} total goals`} icon={Target} tone="blue" />
        <StatCard label="Average progress" value={`${summary.average_progress}%`} detail={`${summary.completed} completed`} icon={TrendingUp} tone="emerald" />
        <StatCard label="Needs attention" value={attention} detail={`${summary.overdue} overdue`} icon={AlertTriangle} tone="amber" />
        <StatCard label="On track" value={summary.on_track} detail={`${summary.due_soon} due within 14 days`} icon={CheckCircle2} tone="blue" />
      </div>

      <Card>
        <div className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_170px_170px_170px_auto]">
          <Input
            aria-label="Search goals"
            icon={Search}
            value={query}
            onChange={(event) => { setQuery(event.target.value); setPage(1); }}
            placeholder="Search goals or units"
          />
          <Select aria-label="Goal status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </Select>
          <Select aria-label="Goal health" value={health} onChange={(event) => { setHealth(event.target.value); setPage(1); }}>
            <option value="">All health</option>
            <option value="on_track">On track</option>
            <option value="at_risk">At risk</option>
            <option value="off_track">Off track</option>
            <option value="completed">Completed</option>
          </Select>
          <Select aria-label="Goal owner type" value={ownerType} onChange={(event) => { setOwnerType(event.target.value); setPage(1); }}>
            <option value="">All owners</option>
            <option value="organization">Organization</option>
            <option value="department">Department</option>
            <option value="employee">Employee</option>
          </Select>
          <Button type="button" variant="ghost" disabled={!hasFilters} onClick={resetFilters}>
            <X size={15} /> Reset
          </Button>
        </div>
      </Card>

      <Card padded={false}>
        {goals.length === 0 && !loading ? (
          <div className="p-6">
            <EmptyState
              title={hasFilters ? 'No goals match these filters' : 'No goals have been created'}
              description={hasFilters ? 'Reset the filters or broaden the search.' : 'Create a measurable organization, department, or employee outcome.'}
              icon={CircleGauge}
            />
          </div>
        ) : (
          <Table
            columns={columns}
            rows={goals}
            loading={loading}
            sort={sort}
            onSortChange={(value) => { setSort(value); setPage(1); }}
            pagination={{
              page: meta.page || page,
              pageSize: meta.per_page || 15,
              total: meta.total || 0,
              onPageChange: setPage,
              label: 'goals',
            }}
          />
        )}
      </Card>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create a measurable goal"
        description="Set an owner, target, unit, and review period."
        size="xl"
      >
        <GoalForm
          employees={employees}
          departments={departments}
          onSubmit={createGoal}
          loading={saving}
        />
      </Modal>

      <Modal
        open={Boolean(selectedGoal)}
        onClose={() => setSelectedGoal(null)}
        title="Record a goal check-in"
        description="Update progress, health, and the narrative behind the result."
        size="md"
      >
        {selectedGoal && (
          <GoalCheckInForm
            key={selectedGoal.id}
            goal={selectedGoal}
            onSubmit={saveCheckIn}
            loading={saving}
          />
        )}
      </Modal>
    </div>
  );
}
