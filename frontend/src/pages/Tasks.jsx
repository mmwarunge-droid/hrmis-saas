import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  CheckCircle2,
  CircleDashed,
  Clock3,
  FileSignature,
  ListChecks,
  Sparkles,
} from 'lucide-react';

import { onboardingApi } from '../api/onboardingApi';
import { signatureApi } from '../api/signatureApi';
import SignatureTaskCard from '../components/documents/SignatureTaskCard.jsx';
import Alert from '../components/ui/Alert.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import ProgressRing from '../components/ui/ProgressRing.jsx';
import StatCard from '../components/ui/StatCard.jsx';

function isOverdue(value) {
  if (!value) return false;

  const deadline = new Date(value);

  return (
    !Number.isNaN(deadline.getTime())
    && deadline < new Date()
  );
}

export default function Tasks() {
  const [onboardingTasks, setOnboardingTasks] = useState([]);
  const [signatureTasks, setSignatureTasks] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [actionId, setActionId] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(async () => {
    const results = await Promise.allSettled([
      onboardingApi.myTasks(),
      onboardingApi.templates(),
      signatureApi.myTasks(),
    ]);

    if (results[0].status === 'fulfilled') {
      setOnboardingTasks(
        results[0].value.data.items || [],
      );
    } else {
      setError(
        results[0].reason?.error?.message
        || 'Unable to load onboarding tasks',
      );
    }

    if (results[1].status === 'fulfilled') {
      setTemplates(results[1].value.data.items || []);
    }

    if (results[2].status === 'fulfilled') {
      setSignatureTasks(
        results[2].value.data.items || [],
      );
    } else {
      setError(
        results[2].reason?.error?.message
        || 'Unable to load signature tasks',
      );
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const taskCatalog = useMemo(
    () => Object.fromEntries(
      templates.flatMap((template) => (
        (template.tasks || []).map((task) => [
          task.id,
          {
            ...task,
            template: template.name,
          },
        ])
      )),
    ),
    [templates],
  );

  const completed = onboardingTasks.filter(
    (task) => task.status === 'completed',
  ).length;

  const overdue = (
    onboardingTasks.filter(
      (task) => task.status === 'overdue',
    ).length
    + signatureTasks.filter(
      (task) => isOverdue(task.due_at),
    ).length
  );

  const assigned = (
    onboardingTasks.length + signatureTasks.length
  );

  const onboardingCompletion = onboardingTasks.length
    ? Math.round(
      (completed / onboardingTasks.length) * 100,
    )
    : 0;

  const completeOnboarding = async (id) => {
    setActionId(id);
    setError('');
    setSuccess('');

    try {
      await onboardingApi.complete(id);
      setSuccess('Task marked as complete.');
      await load();
    } catch (err) {
      setError(
        err.error?.message
        || 'Task completion failed',
      );
    } finally {
      setActionId('');
    }
  };

  const markViewed = async (id) => {
    try {
      await signatureApi.viewed(id);
      await load();
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to record document review',
      );
    }
  };

  const signDocument = async (id) => {
    setActionId(id);
    setError('');
    setSuccess('');

    try {
      await signatureApi.sign(id);
      setSuccess(
        'Your signature confirmation was recorded.',
      );
      await load();
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to record signature',
      );
    } finally {
      setActionId('');
    }
  };

  const declineDocument = async (id, reason) => {
    setActionId(id);
    setError('');
    setSuccess('');

    try {
      await signatureApi.decline(id, reason);
      setSuccess('The signature request was declined.');
      await load();
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to decline signature request',
      );
    } finally {
      setActionId('');
    }
  };

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Action center"
        title="My tasks"
        description="A single queue for document signatures, onboarding actions, required acknowledgements and people-operations follow-ups."
      />

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          label="Assigned"
          value={assigned}
          detail="Tasks currently in your queue"
          icon={ListChecks}
          tone="blue"
        />
        <StatCard
          label="Documents to sign"
          value={signatureTasks.length}
          detail="Contracts requiring your attention"
          icon={FileSignature}
          tone="violet"
        />
        <StatCard
          label="Overdue"
          value={overdue}
          detail="Items requiring immediate action"
          icon={Clock3}
          tone="rose"
        />
      </div>

      <Alert type="info">
        ACE is currently recording the internal signing workflow,
        recipient consent, timestamps and audit events. Embedded
        document fields and drawn or certificate-backed electronic
        signatures will be enabled through the signing-provider
        integration phase.
      </Alert>

      <Card>
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-cyan-50 text-cyan-700">
            <FileSignature size={18} />
          </span>
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-cyan-700">
              Documents
            </p>
            <h2 className="font-bold">
              Awaiting my signature
            </h2>
          </div>
        </div>

        <div className="mt-5 space-y-3">
          {signatureTasks.length === 0 ? (
            <EmptyState
              title="No documents are waiting"
              description="New contracts and signature requests assigned to you will appear here."
            />
          ) : (
            signatureTasks.map((task) => (
              <SignatureTaskCard
                key={task.id}
                task={task}
                loading={actionId === task.id}
                onViewed={markViewed}
                onSign={signDocument}
                onDecline={declineDocument}
              />
            ))
          )}
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[0.7fr_1.3fr]">
        <Card className="grid place-items-center bg-gradient-to-br from-cyan-50 to-violet-50 text-center">
          <div>
            <ProgressRing
              value={onboardingCompletion}
              size={150}
              stroke={12}
              label="Onboarding completion"
            />
            <p className="mx-auto mt-5 max-w-xs text-sm leading-6 text-slate-600">
              Complete assigned steps to keep employee
              experiences consistent and auditable.
            </p>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-2xl bg-violet-50 text-violet-700">
              <Sparkles size={18} />
            </span>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-violet-700">
                Onboarding
              </p>
              <h2 className="font-bold">
                Assigned workflow tasks
              </h2>
            </div>
          </div>

          <div className="mt-5 space-y-3">
            {onboardingTasks.length === 0 ? (
              <EmptyState
                title="Your onboarding queue is clear"
                description="New onboarding and HR workflow tasks will appear here."
              />
            ) : (
              onboardingTasks.map((task) => {
                const detail = taskCatalog[task.task_id];
                const done = task.status === 'completed';

                return (
                  <div
                    key={task.id}
                    className="flex flex-col gap-4 rounded-2xl border border-slate-100 p-4 sm:flex-row sm:items-center"
                  >
                    <span
                      className={`grid h-11 w-11 shrink-0 place-items-center rounded-2xl ${
                        done
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-slate-100 text-slate-500'
                      }`}
                    >
                      {done
                        ? <CheckCircle2 size={20} />
                        : <CircleDashed size={20} />}
                    </span>

                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-slate-900">
                        {detail?.title || 'Onboarding task'}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {detail?.template || 'Employee workflow'}
                        {' · '}
                        Due {task.due_date || 'not set'}
                      </p>
                    </div>

                    <Badge
                      tone={
                        done
                          ? 'green'
                          : task.status === 'overdue'
                            ? 'red'
                            : 'amber'
                      }
                    >
                      {task.status.replaceAll('_', ' ')}
                    </Badge>

                    {!done && (
                      <Button
                        size="sm"
                        variant="soft"
                        disabled={actionId === task.id}
                        onClick={() => completeOnboarding(
                          task.id,
                        )}
                      >
                        Mark complete
                      </Button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
