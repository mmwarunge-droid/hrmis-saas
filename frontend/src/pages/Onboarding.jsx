import { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, CircleDashed, ClipboardCheck, Clock3 } from 'lucide-react';

import { onboardingApi } from '../api/onboardingApi.js';
import OnboardingAdminPanel from '../components/onboarding/OnboardingAdminPanel.jsx';
import OnboardingChecklist from '../components/onboarding/OnboardingChecklist.jsx';
import Alert from '../components/ui/Alert.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import Tabs from '../components/ui/Tabs.jsx';
import { useToast } from '../context/ToastContext.jsx';
import usePermissions from '../hooks/usePermissions.js';

export default function Onboarding() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [completingId, setCompletingId] = useState('');
  const [error, setError] = useState('');
  const [view, setView] = useState('my-work');
  const { hasPermission } = usePermissions();
  const canAdminister = hasPermission('onboarding:create');
  const toast = useToast();

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

  useEffect(() => { load(); }, [load]);

  const metrics = useMemo(() => ({
    completed: tasks.filter((task) => task.status === 'completed').length,
    open: tasks.filter((task) => !['completed', 'waived'].includes(task.status)).length,
    overdue: tasks.filter((task) => task.status === 'overdue').length,
  }), [tasks]);

  const complete = async (id) => {
    const task = tasks.find((item) => item.id === id);
    setCompletingId(id);
    setError('');
    try {
      await onboardingApi.complete(id, {
        acknowledged: Boolean(task?.requires_acknowledgement),
      });
      toast.success('Onboarding task completed.');
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
        eyebrow="Employee journey"
        title="Onboarding"
        description="Complete assigned new-hire work and administer reusable onboarding plans from one workflow."
      />

      {canAdminister && (
        <Tabs
          ariaLabel="Onboarding views"
          idPrefix="onboarding-views"
          value={view}
          onChange={setView}
          items={[
            { value: 'my-work', label: 'My onboarding work', count: metrics.open },
            { value: 'administration', label: 'Administration' },
          ]}
        />
      )}

      <section
        id={canAdminister ? `onboarding-views-panel-${view}` : undefined}
        role={canAdminister ? 'tabpanel' : undefined}
        aria-labelledby={canAdminister ? `onboarding-views-tab-${view}` : undefined}
        tabIndex={canAdminister ? 0 : undefined}
      >
        {view === 'administration' && canAdminister ? (
          <OnboardingAdminPanel />
        ) : (
          <>
            {error && <Alert type="error">{error}</Alert>}
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
          </>
        )}
      </section>
    </div>
  );
}
