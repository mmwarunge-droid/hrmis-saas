import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CheckCircle2,
  CircleDashed,
  Clock3,
  Plus,
  UserPlus,
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
import Pagination from '../ui/Pagination.jsx';
import Select from '../ui/Select.jsx';
import StatCard from '../ui/StatCard.jsx';

const emptyTask = () => ({
  title: '',
  description: '',
  assignee_role: 'EMPLOYEE',
  due_days_after_start: 0,
  required: true,
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
      tasks: current.tasks.map((task, taskIndex) => (
        taskIndex === index ? { ...task, [field]: value } : task
      )),
    }));
  };

  const createTemplate = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await onboardingApi.createTemplate({
        ...templateForm,
        tasks: templateForm.tasks.map((task) => ({
          ...task,
          due_days_after_start: Number(task.due_days_after_start || 0),
        })),
      });
      setTemplateForm({ name: '', description: '', tasks: [emptyTask()] });
      toast.success('Onboarding template created.');
      await load();
    } catch (err) {
      setError(err.error?.message || 'Template creation failed.');
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
                      label="Task description"
                      value={task.description}
                      onChange={(event) => updateTask(index, 'description', event.target.value)}
                    />
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
            <div key={assignment.id} className="grid gap-3 px-4 py-4 lg:grid-cols-[1.2fr_1.4fr_0.8fr_0.8fr] lg:items-center">
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
              <Select
                aria-label={`Update ${assignment.task_title} status`}
                value={assignment.status}
                disabled={saving}
                onChange={(event) => updateStatus(assignment, event.target.value)}
              >
                <option value="pending">Pending</option>
                <option value="in_progress">In progress</option>
                <option value="overdue">Overdue</option>
                <option value="completed">Completed</option>
                <option value="waived">Waived</option>
              </Select>
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
    </div>
  );
}
