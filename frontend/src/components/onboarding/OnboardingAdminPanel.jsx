import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CheckCircle2,
  CircleDashed,
  Clock3,
  FileText,
  History,
  Plus,
  RotateCcw,
  UserPlus,
  Video,
  X,
} from 'lucide-react';
import { employeeApi } from '../../api/employeeApi.js';
import { onboardingApi } from '../../api/onboardingApi.js';
import { useToast } from '../../context/ToastContext.jsx';
import Alert from '../ui/Alert.jsx';
import Badge from '../ui/Badge.jsx';
import Button from '../ui/Button.jsx';
import Card from '../ui/Card.jsx';
import Input from '../ui/Input.jsx';
import Modal from '../ui/Modal.jsx';
import Pagination from '../ui/Pagination.jsx';
import Select from '../ui/Select.jsx';
import StatCard from '../ui/StatCard.jsx';

function readVideoDuration(file) {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    const objectUrl = URL.createObjectURL(file);

    const cleanup = () => {
      video.onloadedmetadata = null;
      video.onerror = null;
      URL.revokeObjectURL(objectUrl);
      video.removeAttribute('src');
      video.load();
    };

    video.preload = 'metadata';
    video.onloadedmetadata = () => {
      const duration = Number(video.duration);
      cleanup();

      if (!Number.isFinite(duration) || duration <= 0) {
        reject(new Error('Unable to determine the training video duration.'));
        return;
      }
      resolve(duration);
    };
    video.onerror = () => {
      cleanup();
      reject(new Error('Unable to read the selected training video.'));
    };
    video.src = objectUrl;
  });
}


const emptyTask = () => ({
  title: '',
  description: '',
  task_type: 'action',
  resource_file: null,
  assignee_role: 'EMPLOYEE',
  due_days_after_start: 0,
  required: true,
  requires_acknowledgement: false,
  max_attempts: 1,
});

export default function OnboardingAdminPanel() {
  const [templates, setTemplates] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [summary, setSummary] = useState({
    total: 0,
    open: 0,
    overdue: 0,
    completed: 0,
  });
  const [meta, setMeta] = useState({ page: 1, pages: 1, total: 0 });
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [templateForm, setTemplateForm] = useState({
    name: '',
    description: '',
    tasks: [emptyTask()],
  });
  const [assignmentForm, setAssignmentForm] = useState({
    employee_id: '',
    template_id: '',
  });
  const [retakeAssignment, setRetakeAssignment] = useState(null);
  const [retakeForm, setRetakeForm] = useState({
    due_date: '',
    reason: '',
    grant_additional_attempts: 0,
  });
  const [attemptHistory, setAttemptHistory] = useState([]);
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [templateResponse, employeeResponse, assignmentResponse, summaryResponse] = await Promise.all([
        onboardingApi.templates(),
        employeeApi.options(),
        onboardingApi.assignments({ page, per_page: 15, status: status || undefined }),
        onboardingApi.summary(),
      ]);
      setTemplates(templateResponse.data.items || []);
      setEmployees(employeeResponse.data.items || []);
      setAssignments(assignmentResponse.data.items || []);
      setMeta(assignmentResponse.data.meta || { page, pages: 1, total: 0 });
      setSummary(summaryResponse.data);
      setError('');
    } catch (err) {
      setError(err.error?.message || 'Unable to load onboarding administration.');
    } finally {
      setLoading(false);
    }
  }, [page, status]);

  useEffect(() => { load(); }, [load]);

  const activeTemplates = useMemo(
    () => templates.filter((template) => template.is_active),
    [templates],
  );

  const updateTask = (index, field, value) => {
    setTemplateForm((current) => ({
      ...current,
      tasks: current.tasks.map((task, taskIndex) => {
        if (taskIndex !== index) return task;

        if (field === 'task_type') {
          return {
            ...task,
            task_type: value,
            resource_file: null,
            requires_acknowledgement: value !== 'action',
          };
        }

        return { ...task, [field]: value };
      }),
    }));
  };

  const createTemplate = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const tasks = await Promise.all(
        templateForm.tasks.map(async (task) => {
          let resourceId = null;

          if (task.task_type !== 'action') {
            if (!task.resource_file) {
              throw new Error(
                `Upload a ${task.task_type} for “${task.title || 'this task'}”.`,
              );
            }

            const formData = new FormData();
            formData.append('file', task.resource_file);
            if (task.task_type === 'video') {
              const duration = await readVideoDuration(
                task.resource_file,
              );
              formData.append(
                'duration_seconds',
                String(duration),
              );
            }
            const resourceResponse = await onboardingApi.uploadResource(formData);
            resourceId = resourceResponse.data.id;
          }

          return {
            title: task.title,
            description: task.description || null,
            task_type: task.task_type,
            resource_id: resourceId,
            assignee_role: task.assignee_role,
            due_days_after_start: Number(task.due_days_after_start || 0),
            required: task.required,
            requires_acknowledgement: task.requires_acknowledgement,
            max_attempts: Number(task.max_attempts || 1),
          };
        }),
      );

      await onboardingApi.createTemplate({
        name: templateForm.name,
        description: templateForm.description,
        tasks,
      });
      setTemplateForm({ name: '', description: '', tasks: [emptyTask()] });
      toast.success('Onboarding template created.');
      await load();
    } catch (err) {
      setError(err.error?.message || err.message || 'Template creation failed.');
    } finally {
      setSaving(false);
    }
  };

  const assign = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await onboardingApi.assign(assignmentForm);
      setAssignmentForm({ employee_id: '', template_id: '' });
      toast.success('Onboarding plan assigned.');
      await load();
    } catch (err) {
      setError(err.error?.message || 'Onboarding assignment failed.');
    } finally {
      setSaving(false);
    }
  };

  const updateStatus = async (assignment, nextStatus) => {
    setSaving(true);
    try {
      await onboardingApi.updateAssignment(assignment.id, {
        status: nextStatus,
      });
      toast.success('Assignment status updated.');
      await load();
    } catch (err) {
      setError(err.error?.message || 'Assignment update failed.');
    } finally {
      setSaving(false);
    }
  };

  const openRetake = async (assignment) => {
    setRetakeAssignment(assignment);
    setRetakeForm({
      due_date: assignment.due_date || '',
      reason: '',
      grant_additional_attempts: (
        assignment.attempts_remaining > 0 ? 0 : 1
      ),
    });
    setAttemptHistory([]);
    setError('');
    try {
      const response = await onboardingApi.attempts(assignment.id);
      setAttemptHistory(response.data.items || []);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to load training attempt history.',
      );
    }
  };

  const submitRetake = async (event) => {
    event.preventDefault();
    if (!retakeAssignment) return;

    setSaving(true);
    setError('');
    try {
      await onboardingApi.retake(retakeAssignment.id, {
        reason: retakeForm.reason,
        due_date: retakeForm.due_date || null,
        grant_additional_attempts: Number(
          retakeForm.grant_additional_attempts || 0,
        ),
      });
      toast.success('Training retake assigned.');
      setRetakeAssignment(null);
      setAttemptHistory([]);
      await load();
    } catch (err) {
      setError(err.error?.message || 'Unable to resubmit training.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {error && <Alert type="error">{error}</Alert>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Assigned tasks" value={summary.total} detail="All onboarding work" icon={UserPlus} tone="blue" loading={loading} />
        <StatCard label="Open" value={summary.open} detail="Pending or in progress" icon={CircleDashed} tone="amber" loading={loading} />
        <StatCard label="Overdue" value={summary.overdue} detail="Needs intervention" icon={Clock3} tone="rose" loading={loading} />
        <StatCard label="Completed" value={summary.completed} detail="Finished assignments" icon={CheckCircle2} tone="emerald" loading={loading} />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-blue-700">Templates</p>
            <h2 className="mt-1 text-lg font-bold text-slate-950">Create a reusable onboarding plan</h2>
          </div>
          <form className="mt-5 space-y-4" onSubmit={createTemplate}>
            <Input
              label="Template name"
              value={templateForm.name}
              onChange={(event) => setTemplateForm((current) => ({ ...current, name: event.target.value }))}
              required
            />
            <Input
              label="Description"
              value={templateForm.description}
              onChange={(event) => setTemplateForm((current) => ({ ...current, description: event.target.value }))}
            />
            <div className="space-y-3">
              {templateForm.tasks.map((task, index) => (
                <div key={`task-${index}`} className="rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-bold text-slate-900">Task {index + 1}</p>
                    {templateForm.tasks.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setTemplateForm((current) => ({
                          ...current,
                          tasks: current.tasks.filter((_, taskIndex) => taskIndex !== index),
                        }))}
                        className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-700"
                        aria-label={`Remove task ${index + 1}`}
                      >
                        <X size={15} />
                      </button>
                    )}
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <Input
                      label="Task title"
                      value={task.title}
                      onChange={(event) => updateTask(index, 'title', event.target.value)}
                      required
                    />
                    <Select
                      label="Requirement type"
                      value={task.task_type}
                      onChange={(event) => updateTask(index, 'task_type', event.target.value)}
                    >
                      <option value="action">Action / checklist</option>
                      <option value="document">Read & acknowledge</option>
                      <option value="video">Training video</option>
                    </Select>
                    <Select
                      label="Responsible role"
                      value={task.assignee_role}
                      onChange={(event) => updateTask(index, 'assignee_role', event.target.value)}
                    >
                      <option value="EMPLOYEE">Employee</option>
                      <option value="MANAGER">Manager</option>
                      <option value="CLIENT_ADMIN">Client administrator</option>
                      <option value="HR_CONSULTANT">HR consultant</option>
                    </Select>
                    <Input
                      label="Due days after hire"
                      type="number"
                      min="0"
                      value={task.due_days_after_start}
                      onChange={(event) => updateTask(index, 'due_days_after_start', event.target.value)}
                    />
                    <Input
                      label="Maximum attempts"
                      type="number"
                      min="1"
                      max="20"
                      value={task.max_attempts}
                      onChange={(event) => updateTask(
                        index,
                        'max_attempts',
                        event.target.value,
                      )}
                      hint="Applies to retakes of this requirement."
                    />
                    <Input
                      label="Task description"
                      value={task.description}
                      onChange={(event) => updateTask(index, 'description', event.target.value)}
                    />
                    {task.task_type !== 'action' && (
                      <label className="md:col-span-2 block text-sm font-semibold text-slate-700">
                        <span className="flex items-center gap-2">
                          {task.task_type === 'video'
                            ? <Video size={16} />
                            : <FileText size={16} />}
                          {task.task_type === 'video'
                            ? 'Training video'
                            : 'Required reading'}
                        </span>
                        <input
                          className="mt-2 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                          type="file"
                          accept={task.task_type === 'video' ? '.mp4,.webm,video/mp4,video/webm' : '.pdf,.doc,.docx,.txt'}
                          onChange={(event) => updateTask(
                            index,
                            'resource_file',
                            event.target.files?.[0] || null,
                          )}
                          required
                        />
                        <span className="mt-1 block text-xs font-normal text-slate-500">
                          {task.task_type === 'video'
                            ? 'MP4 or WebM. Keep demo uploads under 10 MB.'
                            : 'PDF, Word or text. The employee will explicitly acknowledge completion.'}
                        </span>
                      </label>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap justify-between gap-3">
              <Button
                variant="secondary"
                onClick={() => setTemplateForm((current) => ({
                  ...current,
                  tasks: [...current.tasks, emptyTask()],
                }))}
              >
                <Plus size={15} /> Add task
              </Button>
              <Button type="submit" disabled={saving}>Create template</Button>
            </div>
          </form>
        </Card>

        <Card>
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-violet-700">Assignment</p>
            <h2 className="mt-1 text-lg font-bold text-slate-950">Start an employee onboarding plan</h2>
          </div>
          <form className="mt-5 space-y-4" onSubmit={assign}>
            <Select
              label="Employee"
              value={assignmentForm.employee_id}
              onChange={(event) => setAssignmentForm((current) => ({ ...current, employee_id: event.target.value }))}
              required
            >
              <option value="">Select employee</option>
              {employees.map((employee) => (
                <option key={employee.id} value={employee.id}>{employee.full_name}</option>
              ))}
            </Select>
            <Select
              label="Template"
              value={assignmentForm.template_id}
              onChange={(event) => setAssignmentForm((current) => ({ ...current, template_id: event.target.value }))}
              required
            >
              <option value="">Select template</option>
              {activeTemplates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name} · {template.tasks?.length || 0} tasks
                </option>
              ))}
            </Select>
            <Button type="submit" disabled={saving || !assignmentForm.employee_id || !assignmentForm.template_id}>
              <UserPlus size={16} /> Assign onboarding
            </Button>
          </form>

          <div className="mt-7 border-t border-slate-200 pt-5">
            <p className="text-sm font-bold text-slate-900">Available templates</p>
            <div className="mt-3 space-y-2">
              {activeTemplates.map((template) => (
                <div key={template.id} className="rounded-lg border border-slate-200 px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-slate-900">{template.name}</p>
                    <Badge tone="blue">{template.tasks?.length || 0} tasks</Badge>
                  </div>
                  {template.description && <p className="mt-1 text-xs text-slate-500">{template.description}</p>}
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>

      <Card className="p-0">
        <div className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-blue-700">Progress</p>
            <h2 className="mt-1 text-lg font-bold text-slate-950">Onboarding assignments</h2>
          </div>
          <Select
            aria-label="Filter onboarding assignments by status"
            value={status}
            onChange={(event) => { setStatus(event.target.value); setPage(1); }}
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In progress</option>
            <option value="overdue">Overdue</option>
            <option value="completed">Completed</option>
            <option value="waived">Waived</option>
          </Select>
        </div>
        <div className="divide-y divide-slate-100 border-t border-slate-200">
          {assignments.map((assignment) => (
            <div
              key={assignment.id}
              className="grid gap-3 px-4 py-4 lg:grid-cols-[1.1fr_1.35fr_0.8fr_0.9fr_1fr] lg:items-center"
            >
              <div>
                <p className="font-semibold text-slate-900">{assignment.employee_name}</p>
                <p className="text-xs text-slate-500">{assignment.employee_number}</p>
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800">{assignment.task_title}</p>
                <p className="text-xs text-slate-500">{assignment.template_name}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Due</p>
                <p className="text-sm font-medium text-slate-800">{assignment.due_date || 'Not set'}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Attempt</p>
                <p className="text-sm font-semibold text-slate-800">
                  {assignment.current_attempt_number}
                  {' of '}
                  {assignment.attempt_limit}
                </p>
                <p className="text-xs text-slate-500">
                  {assignment.attempts_remaining} remaining
                </p>
              </div>
              <Select
                aria-label={`Update ${assignment.task_title} status`}
                value={assignment.status}
                disabled={saving}
                onChange={(event) => updateStatus(assignment, event.target.value)}
              >
                <option value="pending">Pending</option>
                <option value="in_progress">In progress</option>
                <option value="overdue">Overdue</option>
                {(
                  assignment.task_type !== 'video'
                  || assignment.status === 'completed'
                ) && (
                  <option value="completed">Completed</option>
                )}
                <option value="waived">Waived</option>
              </Select>
              <Button
                type="button"
                size="sm"
                variant="soft"
                disabled={saving}
                onClick={() => openRetake(assignment)}
              >
                <RotateCcw size={14} />
                {assignment.attempts_remaining > 0
                  ? 'Resubmit training'
                  : 'Grant attempt'}
              </Button>
            </div>
          ))}
          {!loading && assignments.length === 0 && (
            <p className="px-4 py-10 text-center text-sm text-slate-500">No onboarding assignments match this view.</p>
          )}
        </div>
        {meta.total > 0 && (
          <div className="border-t border-slate-200 p-4">
            <Pagination
              page={meta.page || page}
              pageSize={15}
              total={meta.total || 0}
              onPageChange={setPage}
              label="onboarding assignments"
            />
          </div>
        )}
      </Card>

      <Modal
        open={Boolean(retakeAssignment)}
        title={retakeAssignment?.attempts_remaining > 0
          ? 'Resubmit training'
          : 'Grant additional attempt'}
        description={
          "Reuse the existing training content and preserve the employee's "
          + 'previous attempt history.'
        }
        onClose={() => !saving && setRetakeAssignment(null)}
      >
        {retakeAssignment && (
          <form className="space-y-5" onSubmit={submitRetake}>
            <div className="grid gap-3 rounded-lg bg-slate-50 p-4 sm:grid-cols-2">
              <div>
                <p className="text-xs text-slate-500">Employee</p>
                <p className="font-semibold text-slate-900">
                  {retakeAssignment.employee_name}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Training</p>
                <p className="font-semibold text-slate-900">
                  {retakeAssignment.task_title}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Content</p>
                <p className="text-sm text-slate-700">
                  {retakeAssignment.resource?.original_filename
                    || retakeAssignment.task_type}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Current attempt</p>
                <p className="text-sm text-slate-700">
                  {retakeAssignment.current_attempt_number}
                  {' of '}
                  {retakeAssignment.attempt_limit}
                </p>
              </div>
            </div>

            <Input
              label="Completion deadline"
              type="date"
              value={retakeForm.due_date}
              onChange={(event) => setRetakeForm((current) => ({
                ...current,
                due_date: event.target.value,
              }))}
            />

            {retakeAssignment.attempts_remaining === 0 && (
              <Input
                label="Additional attempts to grant"
                type="number"
                min="1"
                max="10"
                value={retakeForm.grant_additional_attempts}
                onChange={(event) => setRetakeForm((current) => ({
                  ...current,
                  grant_additional_attempts: event.target.value,
                }))}
                required
              />
            )}

            <Input
              label="Reason for resubmission"
              value={retakeForm.reason}
              onChange={(event) => setRetakeForm((current) => ({
                ...current,
                reason: event.target.value,
              }))}
              placeholder="e.g. Repeat compliance training after policy update"
              required
            />

            <div>
              <div className="flex items-center gap-2">
                <History size={15} className="text-slate-500" />
                <p className="text-sm font-bold text-slate-900">
                  Attempt history
                </p>
              </div>
              <div className="mt-2 space-y-2">
                {attemptHistory.map((attempt) => (
                  <div
                    key={attempt.id}
                    className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  >
                    <span>Attempt {attempt.attempt_number}</span>
                    <Badge
                      tone={attempt.status === 'completed'
                        ? 'green'
                        : attempt.status === 'failed'
                          ? 'red'
                          : 'gray'}
                    >
                      {attempt.status}
                    </Badge>
                  </div>
                ))}
                {attemptHistory.length === 0 && (
                  <p className="text-xs text-slate-500">
                    No previous attempts recorded.
                  </p>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setRetakeAssignment(null)}
                disabled={saving}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={saving}>
                <RotateCcw size={15} />
                {retakeAssignment.attempts_remaining > 0
                  ? 'Resubmit'
                  : 'Grant & resubmit'}
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
