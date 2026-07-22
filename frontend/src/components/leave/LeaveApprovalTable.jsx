import Button from '../ui/Button.jsx';
import Table from '../ui/Table.jsx';

export default function LeaveApprovalTable({ requests, onApprove, onReject }) {
  const columns = [
    { key: 'start_date', label: 'Start' },
    { key: 'end_date', label: 'End' },
    { key: 'total_days', label: 'Days' },
    { key: 'status', label: 'Status' },
    { key: 'actions', label: 'Actions', render: (row) => row.status === 'pending' ? <div className="flex gap-2"><Button onClick={() => onApprove(row.id)}>Approve</Button><Button variant="danger" onClick={() => onReject(row.id)}>Reject</Button></div> : null },
  ];
  return <Table columns={columns} rows={requests} empty="No leave requests." />;
}
