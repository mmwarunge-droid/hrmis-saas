import { CheckCircle2, CircleDashed } from 'lucide-react';

import Badge from '../ui/Badge.jsx';
import Button from '../ui/Button.jsx';
import Table from '../ui/Table.jsx';

function formatDate(value) {
  if (!value) return 'No due date';
  return new Intl.DateTimeFormat('en', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(`${value}T00:00:00`));
}

function statusTone(status) {
  if (status === 'completed') return 'green';
  if (status === 'overdue') return 'red';
  if (status === 'in_progress') return 'amber';
  return 'slate';
}

export default function OnboardingChecklist({
  tasks = [],
  onComplete,
  completingId = '',
  loading = false,
}) {
  const columns = [
    {
      key: 'task_id',
      label: 'Task',
      sortable: true,
      render: (row) => (
        <div className="flex items-center gap-3">
          <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${row.status === 'completed' ? 'bg-emerald-50 text-emerald-700' : 'bg-blue-50 text-blue-700'}`}>
            {row.status === 'completed' ? <CheckCircle2 size={17} /> : <CircleDashed size={17} />}
          </span>
          <div className="min-w-0">
            <p className="font-semibold text-slate-900">Onboarding task</p>
            <p className="truncate text-xs text-slate-500">Reference {String(row.task_id || '').slice(0, 8)}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'due_date',
      label: 'Due date',
      sortable: true,
      render: (row) => formatDate(row.due_date),
    },
    {
      key: 'status',
      label: 'Status',
      sortable: true,
      render: (row) => (
        <Badge tone={statusTone(row.status)}>{String(row.status || 'pending').replaceAll('_', ' ')}</Badge>
      ),
    },
    {
      key: 'actions',
      label: '',
      cellClassName: 'text-right',
      render: (row) => row.status !== 'completed' ? (
        <Button
          size="sm"
          variant="secondary"
          disabled={completingId === row.id}
          onClick={() => onComplete(row.id)}
        >
          {completingId === row.id ? 'Completing…' : 'Mark complete'}
        </Button>
      ) : <span className="text-xs font-semibold text-emerald-700">Done</span>,
    },
  ];

  return (
    <Table
      caption="Onboarding tasks"
      columns={columns}
      rows={tasks}
      loading={loading}
      pageSize={10}
      density="compact"
      empty="No onboarding tasks are assigned to you."
    />
  );
}
