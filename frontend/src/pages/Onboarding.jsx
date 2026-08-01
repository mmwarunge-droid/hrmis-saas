import { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, CircleDashed, ClipboardCheck, Clock3 } from 'lucide-react';

import { onboardingApi } from '../api/onboardingApi';
import OnboardingChecklist from '../components/onboarding/OnboardingChecklist.jsx';
import Alert from '../components/ui/Alert.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import StatCard from '../components/ui/StatCard.jsx';

export default function Onboarding() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [completingId, setCompletingId] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const response = await onboardingApi.myTasks();
      setTasks(response.data.items || []);
    } catch (err) {
      setError(err.error?.message || 'Unable to load onboarding tasks.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const metrics = useMemo(() => ({
    completed: tasks.filter((task) => task.status === 'completed').length,
    open: tasks.filter((task) => !['completed', 'waived'].includes(task.status)).length,
    overdue: tasks.filter((task) => task.status === 'overdue').length,
  }), [tasks]);

  const complete = async (id) => {
    setCompletingId(id);
    setError('');
    setMessage('');
    try {
      await onboardingApi.complete(id);
      setMessage('Onboarding task completed.');
      await load();
    } catch (err) {
      setError(err.error?.message || 'The onboarding task could not be completed.');
    } finally {
      setCompletingId('');
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="My work"
        title="Onboarding"
        description="Review assigned new-hire activities, due dates and completion progress in one place."
      />

      {error && <Alert type="error">{error}</Alert>}
      {message && <Alert type="success">{message}</Alert>}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Assigned" value={tasks.length} detail="Tasks in your checklist" icon={ClipboardCheck} tone="blue" loading={loading} />
        <StatCard label="Open" value={metrics.open} detail="Still requiring action" icon={CircleDashed} tone="amber" loading={loading} />
        <StatCard label="Completed" value={metrics.completed} detail={metrics.overdue ? `${metrics.overdue} overdue` : 'No overdue tasks'} icon={metrics.overdue ? Clock3 : CheckCircle2} tone={metrics.overdue ? 'rose' : 'emerald'} loading={loading} />
      </div>

      <OnboardingChecklist
        tasks={tasks}
        loading={loading}
        completingId={completingId}
        onComplete={complete}
      />
    </div>
  );
}
