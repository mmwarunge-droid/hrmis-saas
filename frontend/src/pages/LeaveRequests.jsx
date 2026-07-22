import { useEffect, useState } from 'react';
import { employeeApi } from '../api/employeeApi';
import { leaveApi } from '../api/leaveApi';
import LeaveApprovalTable from '../components/leave/LeaveApprovalTable.jsx';
import LeaveRequestForm from '../components/leave/LeaveRequestForm.jsx';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Modal from '../components/ui/Modal.jsx';
import Spinner from '../components/ui/Spinner.jsx';

export default function LeaveRequests() {
  const [requests, setRequests] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [types, setTypes] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = async () => { try { const [r, e, t] = await Promise.all([leaveApi.requests(), employeeApi.list(), leaveApi.types()]); setRequests(r.data.items); setEmployees(e.data.items); setTypes(t.data.items); } catch (err) { setError(err.error?.message || 'Load failed'); } finally { setLoading(false); } };
  useEffect(() => { load(); }, []);
  const submit = async (payload) => { await leaveApi.submit(payload); setOpen(false); await load(); };
  const decide = async (id, approved) => { approved ? await leaveApi.approve(id) : await leaveApi.reject(id); await load(); };
  return <div className="space-y-6"><div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold">Leave Requests</h1><p className="text-slate-500">PTO workflow and approvals.</p></div><Button onClick={() => setOpen(true)}>New Request</Button></div>{error && <Alert type="error">{error}</Alert>}{loading ? <Spinner /> : <LeaveApprovalTable requests={requests} onApprove={(id) => decide(id, true)} onReject={(id) => decide(id, false)} />}<Modal title="Submit Leave Request" open={open} onClose={() => setOpen(false)}><LeaveRequestForm employees={employees} leaveTypes={types} onSubmit={submit} /></Modal></div>;
}
