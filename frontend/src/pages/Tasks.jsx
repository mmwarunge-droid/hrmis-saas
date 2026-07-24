import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, CircleDashed, Clock3, ListChecks, Sparkles } from 'lucide-react';
import { onboardingApi } from '../api/onboardingApi';
import Alert from '../components/ui/Alert.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import ProgressRing from '../components/ui/ProgressRing.jsx';
import StatCard from '../components/ui/StatCard.jsx';

export default function Tasks() {
  const [tasks, setTasks] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [error, setError] = useState('');

  const load = async () => {
    const results = await Promise.allSettled([onboardingApi.myTasks(), onboardingApi.templates()]);
    if (results[0].status === 'fulfilled') setTasks(results[0].value.data.items || []);
    else setError(results[0].reason?.error?.message || 'Unable to load assigned tasks');
    if (results[1].status === 'fulfilled') setTemplates(results[1].value.data.items || []);
  };
  useEffect(() => {
    let cancelled = false;

    Promise.allSettled([
      onboardingApi.myTasks(),
      onboardingApi.templates(),
    ]).then((results) => {
      if (cancelled) return;

      if (results[0].status === 'fulfilled') {
        setTasks(results[0].value.data.items || []);
      } else {
        setError(
          results[0].reason?.error?.message
          || 'Unable to load assigned tasks',
        );
      }

      if (results[1].status === 'fulfilled') {
        setTemplates(results[1].value.data.items || []);
      }
    });

    return () => {
      cancelled = true;
    };
  }, []);

  const taskCatalog = useMemo(() => Object.fromEntries(templates.flatMap((template) => (template.tasks || []).map((task) => [task.id, { ...task, template: template.name }]))), [templates]);
  const completed = tasks.filter((task) => task.status === 'completed').length;
  const overdue = tasks.filter((task) => task.status === 'overdue').length;
  const completion = tasks.length ? Math.round((completed / tasks.length) * 100) : 0;

  const complete = async (id) => {
    try {
      await onboardingApi.complete(id);
      await load();
    } catch (err) {
      setError(err.error?.message || 'Task completion failed');
    }
  };

  return (
    <div className="space-y-7">
      <PageHeader eyebrow="Action center" title="My tasks" description="A single queue for onboarding actions, required acknowledgements and people operations follow-ups." />
      {error && <Alert type="error">{error}</Alert>}
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Assigned" value={tasks.length} detail="Tasks currently in your queue" icon={ListChecks} tone="blue" />
        <StatCard label="Completed" value={completed} detail={`${completion}% completion rate`} icon={CheckCircle2} tone="emerald" />
        <StatCard label="Overdue" value={overdue} detail="Items requiring immediate action" icon={Clock3} tone="rose" />
      </div>
      <div className="grid gap-6 xl:grid-cols-[0.7fr_1.3fr]">
        <Card className="grid place-items-center bg-gradient-to-br from-cyan-50 to-violet-50 text-center">
          <div>
            <ProgressRing value={completion} size={150} stroke={12} label="Task completion" />
            <p className="mx-auto mt-5 max-w-xs text-sm leading-6 text-slate-600">Complete assigned steps to keep employee experiences consistent and auditable.</p>
          </div>
        </Card>
        <Card>
          <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-2xl bg-violet-50 text-violet-700"><Sparkles size={18} /></span><div><p className="text-xs font-bold uppercase tracking-wider text-violet-700">Assigned to me</p><h2 className="font-bold">Work queue</h2></div></div>
          <div className="mt-5 space-y-3">
            {tasks.length === 0 ? <EmptyState title="Your queue is clear" description="New onboarding and HR workflow tasks will appear here." /> : tasks.map((task) => {
              const detail = taskCatalog[task.task_id];
              const done = task.status === 'completed';
              return (
                <div key={task.id} className="flex flex-col gap-4 rounded-2xl border border-slate-100 p-4 sm:flex-row sm:items-center">
                  <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-2xl ${done ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>{done ? <CheckCircle2 size={20} /> : <CircleDashed size={20} />}</span>
                  <div className="min-w-0 flex-1"><p className="font-semibold text-slate-900">{detail?.title || 'Onboarding task'}</p><p className="mt-1 text-xs text-slate-500">{detail?.template || 'Employee workflow'} · Due {task.due_date || 'not set'}</p></div>
                  <Badge tone={done ? 'green' : task.status === 'overdue' ? 'red' : 'amber'}>{task.status.replaceAll('_', ' ')}</Badge>
                  {!done && <Button size="sm" variant="soft" onClick={() => complete(task.id)}>Mark complete</Button>}
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    </div>
  );
}
