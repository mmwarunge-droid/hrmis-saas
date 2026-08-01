import { useCallback, useEffect, useMemo, useState } from 'react';
import { Clock3, LogIn, LogOut, TimerReset } from 'lucide-react';
import { attendanceApi } from '../api/attendanceApi';
import Alert from '../components/ui/Alert.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import Table from '../components/ui/Table.jsx';
import usePermissions from '../hooks/usePermissions.js';

function formatTime(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('en', { hour: '2-digit', minute: '2-digit' }).format(new Date(value));
}

export default function Attendance() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { hasPermission } = usePermissions();
  const canRead = hasPermission('attendance:read');
  const canWrite = hasPermission('attendance:write');

  const load = useCallback(async () => {
    setError('');
    try {
      const response = await attendanceApi.list();
      setRows(response.data.items || []);
    } catch (err) {
      setError(err.error?.message || 'Unable to load attendance');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!canRead) {
      setLoading(false);
      return;
    }
    load();
  }, [canRead, load]);

  const today = new Date().toISOString().slice(0, 10);
  const todayRecord = rows.find((row) => row.work_date === today);
  const completeDays = useMemo(() => rows.filter((row) => row.check_in_at && row.check_out_at).length, [rows]);

  const perform = async (action) => {
    setError('');
    try {
      if (action === 'in') await attendanceApi.checkIn();
      else await attendanceApi.checkOut();
      if (canRead) await load();
    } catch (err) {
      setError(err.error?.message || 'Attendance action failed');
    }
  };

  const columns = [
    { key: 'work_date', label: 'Date', sortable: true },
    { key: 'check_in_at', label: 'Check in', sortable: true, render: (row) => formatTime(row.check_in_at) },
    { key: 'check_out_at', label: 'Check out', sortable: true, render: (row) => formatTime(row.check_out_at) },
    { key: 'source', label: 'Source', sortable: true, render: (row) => <Badge tone="blue">{row.source?.replaceAll('_', ' ') || 'Unknown'}</Badge> },
    { key: 'status', label: 'Status', sortable: true, render: (row) => <Badge tone={row.check_out_at ? 'green' : row.check_in_at ? 'amber' : 'slate'}>{row.check_out_at ? 'Complete' : row.check_in_at ? 'In progress' : 'Missing'}</Badge> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Time"
        title="Attendance"
        description="Self-service check-in, daily attendance visibility and a clean audit trail of working time."
        actions={canWrite && <div className="flex gap-2"><Button variant="accent" onClick={() => perform('in')}><LogIn size={17} /> Check in</Button><Button variant="secondary" onClick={() => perform('out')}><LogOut size={17} /> Check out</Button></div>}
      />
      {error && <Alert type="error">{error}</Alert>}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Today" value={todayRecord?.check_in_at ? 'Checked in' : 'Not started'} detail={todayRecord?.check_in_at ? `Since ${formatTime(todayRecord.check_in_at)}` : 'Use self-service to start the day'} icon={Clock3} tone={todayRecord?.check_in_at ? 'emerald' : 'amber'} />
        <StatCard label="Completed days" value={completeDays} detail={`${rows.length} records in view`} icon={TimerReset} tone="blue" />
        <StatCard label="Open session" value={todayRecord?.check_in_at && !todayRecord?.check_out_at ? '1' : '0'} detail="Attendance sessions awaiting checkout" icon={LogIn} tone="violet" />
      </div>

      {canRead ? <Table caption="Attendance records" columns={columns} rows={rows} loading={loading} pageSize={15} density="compact" empty="No attendance records yet." /> : (
        <Card className="text-center"><p className="font-semibold text-slate-900">Self-service attendance</p><p className="mt-2 text-sm text-slate-500">Your role can check in and out. Detailed attendance reporting is available to managers and administrators.</p></Card>
      )}
    </div>
  );
}
