import Button from '../ui/Button.jsx';
import Table from '../ui/Table.jsx';

export default function OnboardingChecklist({ tasks, onComplete }) {
  const columns = [
    { key: 'task_id', label: 'Task ID' },
    { key: 'status', label: 'Status' },
    { key: 'due_date', label: 'Due' },
    { key: 'actions', label: 'Actions', render: (row) => row.status !== 'completed' ? <Button onClick={() => onComplete(row.id)}>Complete</Button> : 'Done' },
  ];
  return <Table columns={columns} rows={tasks} empty="No onboarding tasks." />;
}
