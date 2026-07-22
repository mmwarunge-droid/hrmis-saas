import { useEffect, useState } from 'react';
import { userApi } from '../api/userApi';
import Alert from '../components/ui/Alert.jsx';
import Badge from '../components/ui/Badge.jsx';
import Table from '../components/ui/Table.jsx';

export default function Users() {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState('');
  useEffect(() => { userApi.list().then((res) => setUsers(res.data.items)).catch((err) => setError(err.error?.message || 'Load failed')); }, []);
  const columns = [{ key: 'full_name', label: 'Name' }, { key: 'email', label: 'Email' }, { key: 'roles', label: 'Roles', render: (row) => <div className="flex flex-wrap gap-1">{row.roles.map((role) => <Badge key={role}>{role}</Badge>)}</div> }, { key: 'is_active', label: 'Active', render: (row) => row.is_active ? 'Yes' : 'No' }];
  return <div className="space-y-6"><div><h1 className="text-2xl font-bold">Users</h1><p className="text-slate-500">Role-based access management.</p></div>{error && <Alert type="error">{error}</Alert>}<Table columns={columns} rows={users} /></div>;
}
