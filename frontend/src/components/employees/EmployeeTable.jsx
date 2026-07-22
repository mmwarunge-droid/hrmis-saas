import { Link } from 'react-router-dom';
import Table from '../ui/Table.jsx';

export default function EmployeeTable({ employees }) {
  const columns = [
    { key: 'employee_number', label: 'No.' },
    { key: 'full_name', label: 'Name', render: (row) => <Link className="font-semibold text-slate-950 hover:underline" to={`/employees/${row.id}`}>{row.full_name}</Link> },
    { key: 'email', label: 'Email' },
    { key: 'job_title', label: 'Job title' },
    { key: 'employment_status', label: 'Status' },
  ];
  return <Table columns={columns} rows={employees} empty="No employees yet." />;
}
