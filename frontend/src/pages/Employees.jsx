import { useEffect, useState } from 'react';
import { employeeApi } from '../api/employeeApi';
import EmployeeForm from '../components/employees/EmployeeForm.jsx';
import EmployeeTable from '../components/employees/EmployeeTable.jsx';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Modal from '../components/ui/Modal.jsx';
import Spinner from '../components/ui/Spinner.jsx';
import usePermissions from '../hooks/usePermissions';

export default function Employees() {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const { hasPermission } = usePermissions();
  const load = () => employeeApi.list().then((res) => setEmployees(res.data.items)).catch((err) => setError(err.error?.message || 'Load failed')).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);
  const create = async (payload) => { setSaving(true); try { await employeeApi.create(payload); setOpen(false); await load(); } catch (err) { setError(err.error?.message || 'Save failed'); } finally { setSaving(false); } };
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold">Employees</h1><p className="text-slate-500">Employee system of record.</p></div>{hasPermission('employee:create') && <Button onClick={() => setOpen(true)}>Add Employee</Button>}</div>
      {error && <Alert type="error">{error}</Alert>}
      {loading ? <Spinner /> : <EmployeeTable employees={employees} />}
      <Modal title="Create Employee" open={open} onClose={() => setOpen(false)}><EmployeeForm onSubmit={create} loading={saving} /></Modal>
    </div>
  );
}
