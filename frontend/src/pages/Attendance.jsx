import { useEffect, useState } from 'react';
import { attendanceApi } from '../api/attendanceApi';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Table from '../components/ui/Table.jsx';

export default function Attendance() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState('');
  const load = () => attendanceApi.list().then((res) => setRows(res.data.items)).catch((err) => setError(err.error?.message || 'Load failed'));
  useEffect(() => { load(); }, []);
  const columns = [{ key: 'work_date', label: 'Date' }, { key: 'check_in_at', label: 'Check in' }, { key: 'check_out_at', label: 'Check out' }, { key: 'source', label: 'Source' }];
  return <div className="space-y-6"><div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold">Attendance</h1><p className="text-slate-500">Time and attendance records.</p></div><div className="flex gap-2"><Button onClick={() => attendanceApi.checkIn().then(load).catch((err) => setError(err.error?.message))}>Check in</Button><Button variant="secondary" onClick={() => attendanceApi.checkOut().then(load).catch((err) => setError(err.error?.message))}>Check out</Button></div></div>{error && <Alert type="error">{error}</Alert>}<Table columns={columns} rows={rows} /></div>;
}
