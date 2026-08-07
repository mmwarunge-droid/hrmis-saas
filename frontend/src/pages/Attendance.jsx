import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Clock3,
  LogIn,
  LogOut,
  Search,
  TimerReset,
  X,
} from 'lucide-react';
import { attendanceApi } from '../api/attendanceApi';
import Alert from '../components/ui/Alert.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Input from '../components/ui/Input.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import Select from '../components/ui/Select.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import Table from '../components/ui/Table.jsx';
import usePermissions from '../hooks/usePermissions.js';

const PAGE_SIZE = 15;
const EMPTY_META = {
  page: 1,
  per_page: PAGE_SIZE,
  total: 0,
  pages: 1,
};
const EMPTY_SUMMARY = {
  total: 0,
  completed: 0,
  open_sessions: 0,
  today_checked_in: 0,
  today_completed: 0,
  today_open: 0,
};

function formatTime(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('en', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

function recordStatus(record) {
  if (record?.check_out_at) return 'Complete';
  if (record?.check_in_at) return 'In progress';
  return 'Not started';
}

export default function Attendance() {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState(EMPTY_META);
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [todayRecord, setTodayRecord] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const { hasPermission } = usePermissions();
  const canRead = hasPermission('attendance:read');
  const canWrite = hasPermission('attendance:write');

  const filterParams = useMemo(() => ({
    q: query || undefined,
    status: status || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  }), [dateFrom, dateTo, query, status]);

  const loadReadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [recordsResponse, summaryResponse] = await Promise.all([
        attendanceApi.list({
          ...filterParams,
          page,
          per_page: PAGE_SIZE,
          sort: sort?.key || undefined,
          direction: sort?.direction || undefined,
        }),
        attendanceApi.summary(filterParams),
      ]);
      setRows(recordsResponse.data.items || []);
      setMeta(recordsResponse.data.meta || {
        ...EMPTY_META,
        page,
      });
      setSummary(summaryResponse.data || EMPTY_SUMMARY);
    } catch (err) {
      setError(err.error?.message || 'Unable to load attendance');
    } finally {
      setLoading(false);
    }
  }, [filterParams, page, sort]);

  const loadToday = useCallback(async () => {
    try {
      const response = await attendanceApi.today();
      setTodayRecord(response.data || null);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to load today’s attendance status',
      );
    }
  }, []);

  useEffect(() => {
    if (canRead) loadReadData();
  }, [canRead, loadReadData]);

  useEffect(() => {
    if (canWrite) loadToday();
  }, [canWrite, loadToday]);

  const perform = async (action) => {
    setActionLoading(true);
    setError('');
    try {
      const response = action === 'in'
        ? await attendanceApi.checkIn()
        : await attendanceApi.checkOut();
      setTodayRecord(response.data);
      if (canRead) await loadReadData();
    } catch (err) {
      setError(err.error?.message || 'Attendance action failed');
    } finally {
      setActionLoading(false);
    }
  };

  const updateQuery = (value) => {
    setQuery(value);
    setPage(1);
  };

  const updateStatus = (value) => {
    setStatus(value);
    setPage(1);
  };

  const updateDateFrom = (value) => {
    setDateFrom(value);
    setPage(1);
  };

  const updateDateTo = (value) => {
    setDateTo(value);
    setPage(1);
  };

  const updateSort = (value) => {
    setSort(value);
    setPage(1);
  };

  const clearFilters = () => {
    setQuery('');
    setStatus('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const hasFilters = Boolean(query || status || dateFrom || dateTo);
  const ownStatus = recordStatus(todayRecord);
  const columns = [
    {
      key: 'employee_name',
      label: 'Employee',
      sortable: true,
      render: (row) => (
        <div>
          <p className="font-semibold text-slate-900">
            {row.employee_name || 'Unknown employee'}
          </p>
          <p className="text-xs text-slate-500">
            {row.employee_number || 'No employee number'}
          </p>
        </div>
      ),
    },
    { key: 'work_date', label: 'Date', sortable: true },
    {
      key: 'check_in_at',
      label: 'Check in',
      sortable: true,
      render: (row) => formatTime(row.check_in_at),
    },
    {
      key: 'check_out_at',
      label: 'Check out',
      sortable: true,
      render: (row) => formatTime(row.check_out_at),
    },
    {
      key: 'source',
      label: 'Source',
      sortable: true,
      render: (row) => (
        <Badge tone="blue">
          {row.source?.replaceAll('_', ' ') || 'Unknown'}
        </Badge>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      sortable: true,
      render: (row) => (
        <Badge
          tone={
            row.check_out_at
              ? 'green'
              : row.check_in_at
                ? 'amber'
                : 'slate'
          }
        >
          {recordStatus(row)}
        </Badge>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Time"
        title="Attendance"
        description="Self-service check-in, daily attendance visibility and a clean audit trail of working time."
        actions={canWrite && (
          <div className="flex gap-2">
            <Button
              variant="accent"
              disabled={actionLoading || Boolean(todayRecord?.check_in_at)}
              onClick={() => perform('in')}
            >
              <LogIn size={17} />
              Check in
            </Button>
            <Button
              variant="secondary"
              disabled={
                actionLoading
                || !todayRecord?.check_in_at
                || Boolean(todayRecord?.check_out_at)
              }
              onClick={() => perform('out')}
            >
              <LogOut size={17} />
              Check out
            </Button>
          </div>
        )}
      />
      {error && <Alert type="error">{error}</Alert>}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          label="Today"
          value={canWrite ? ownStatus : `${summary.today_checked_in} checked in`}
          detail={
            canWrite
              ? (
                todayRecord?.check_in_at
                  ? `Started at ${formatTime(todayRecord.check_in_at)}`
                  : 'Use self-service to start the day'
              )
              : `${summary.today_completed} complete · ${summary.today_open} open`
          }
          icon={Clock3}
          tone={
            canWrite
              ? (todayRecord?.check_in_at ? 'emerald' : 'amber')
              : 'emerald'
          }
        />
        <StatCard
          label="Completed days"
          value={summary.completed}
          detail={`${summary.total} records in the current view`}
          icon={TimerReset}
          tone="blue"
        />
        <StatCard
          label="Open sessions"
          value={summary.open_sessions}
          detail="Attendance sessions awaiting checkout"
          icon={LogIn}
          tone="violet"
        />
      </div>

      {canRead ? (
        <>
          <Card padded={false}>
            <div className="grid gap-3 p-4 lg:grid-cols-[minmax(0,1fr)_180px_170px_170px_auto] lg:items-center">
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-3 top-3 text-slate-400"
                  size={17}
                />
                <Input
                  aria-label="Search attendance"
                  className="pl-9"
                  placeholder="Search employee or employee number"
                  value={query}
                  onChange={(event) => updateQuery(event.target.value)}
                />
              </div>
              <Select
                aria-label="Attendance status"
                value={status}
                onChange={(event) => updateStatus(event.target.value)}
              >
                <option value="">All statuses</option>
                <option value="complete">Complete</option>
                <option value="in_progress">In progress</option>
              </Select>
              <Input
                aria-label="Attendance start date"
                type="date"
                value={dateFrom}
                onChange={(event) => updateDateFrom(event.target.value)}
              />
              <Input
                aria-label="Attendance end date"
                type="date"
                value={dateTo}
                onChange={(event) => updateDateTo(event.target.value)}
              />
              {hasFilters && (
                <Button size="sm" variant="ghost" onClick={clearFilters}>
                  <X size={15} />
                  Clear
                </Button>
              )}
            </div>
            <div className="border-t border-slate-200 px-4 py-2.5 text-xs text-slate-500">
              Showing {rows.length} of {meta.total} matching attendance records
            </div>
          </Card>

          <Table
            caption="Attendance records"
            columns={columns}
            rows={rows}
            loading={loading}
            density="compact"
            empty="No attendance records match the current filters."
            sort={sort}
            onSortChange={updateSort}
            pagination={{
              page: meta.page,
              pageSize: meta.per_page,
              total: meta.total,
              onPageChange: setPage,
              label: 'attendance records',
            }}
          />
        </>
      ) : (
        <Card className="text-center">
          <p className="font-semibold text-slate-900">
            Self-service attendance
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Check in and out from this page. Detailed team attendance
            reporting is available to managers and administrators.
          </p>
          <p className="mt-4 text-sm font-semibold text-blue-800">
            Today: {ownStatus}
          </p>
        </Card>
      )}
    </div>
  );
}
