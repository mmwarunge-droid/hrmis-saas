import {
  useCallback,
  useEffect,
  useState,
} from 'react';
import {
  CheckCircle2,
  CircleDashed,
  Clock3,
  FileSignature,
  FileText,
  ListChecks,
  Sparkles,
} from 'lucide-react';

import { onboardingApi } from '../api/onboardingApi';
import { signatureApi } from '../api/signatureApi';
import SignatureTaskCard from '../components/documents/SignatureTaskCard.jsx';
import VerifiedTrainingVideo from '../components/onboarding/VerifiedTrainingVideo.jsx';
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
  const [actionId, setActionId] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(async () => {
    const results = await Promise.allSettled([
      onboardingApi.myTasks(),
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
      setSignatureTasks(
        results[1].value.data.items || [],
      );
    } else {
      setError(
        results[1].reason?.error?.message
        || 'Unable to load signature tasks',
      );
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const completed = onboardingTasks.filter(
    (task) => task.status === 'completed',
  ).length;

  const activeSignatureTasks = signatureTasks.filter(
    (task) => ['notified', 'viewed'].includes(task.status),
  );

  const overdue = (
    onboardingTasks.filter(
      (task) => task.status === 'overdue',
    ).length
    + activeSignatureTasks.filter(
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

  const updateOnboardingTask = useCallback((updatedTask) => {
    setOnboardingTasks((current) => current.map(
      (task) => (task.id === updatedTask.id ? updatedTask : task),
    ));
  }, []);

  const completeOnboarding = async (task) => {
    setActionId(task.id);
    setError('');
    setSuccess('');

    try {
      await onboardingApi.complete(task.id, {
        acknowledged: Boolean(task.requires_acknowledgement),
      });
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

  const markOnboardingViewed = async (id) => {
    try {
      await onboardingApi.viewed(id);
      await load();
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to record training activity',
      );
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
    <div className="space-y-6">
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
          value={activeSignatureTasks.length}
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

      <Card>
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-lg bg-blue-50 text-blue-700">
            <FileSignature size={18} />
          </span>
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
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
                onDecline={declineDocument}
              />
            ))
          )}
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[0.7fr_1.3fr]">
        <Card className="grid place-items-center bg-gradient-to-br from-blue-50 to-blue-50 text-center">
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
            <span className="grid h-10 w-10 place-items-center rounded-lg bg-blue-50 text-blue-700">
              <Sparkles size={18} />
            </span>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
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
                const done = task.status === 'completed';

                return (
                  <div
                    key={task.id}
                    className="flex flex-col gap-4 rounded-lg border border-slate-100 p-4 sm:flex-row sm:items-center"
                  >
                    <span
                      className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${
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
                        {task.task_title || 'Onboarding task'}
                      </p>
                      {task.task_description && (
                        <p className="mt-1 text-sm text-slate-600">
                          {task.task_description}
                        </p>
                      )}
                      <p className="mt-1 text-xs text-slate-500">
                        {task.template_name || 'Employee workflow'}
                        {' · '}
                        Due {task.due_date || 'not set'}
                      </p>
                      {task.resource?.resource_type === 'document' && (
                        <a
                          className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-blue-700 hover:underline"
                          href={onboardingApi.resourceContentUrl(
                            task.resource.id,
                            task.tenant_id,
                          )}
                          target="_blank"
                          rel="noreferrer"
                          onClick={() => markOnboardingViewed(task.id)}
                        >
                          <FileText size={16} />
                          Open required reading
                        </a>
                      )}
                      {task.resource?.resource_type === 'video' && (
                        <VerifiedTrainingVideo
                          task={task}
                          onAssignmentUpdate={updateOnboardingTask}
                          onError={setError}
                        />
                      )}
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
                        disabled={
                          actionId === task.id
                          || (
                            task.task_type === 'video'
                            && !task.video_progress?.completion_ready
                          )
                        }
                        onClick={() => completeOnboarding(task)}
                      >
                        {task.requires_acknowledgement
                          ? 'Acknowledge & complete'
                          : 'Mark complete'}
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
