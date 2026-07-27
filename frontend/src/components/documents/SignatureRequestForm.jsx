import { useMemo, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';

import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';

function newRecipient() {
  return {
    employee_id: '',
    role_label: 'Signatory',
    sequence: 1,
  };
}

function toInteger(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export default function SignatureRequestForm({
  document,
  employees = [],
  isSuperAdmin = false,
  loading = false,
  onSubmit,
}) {
  const [form, setForm] = useState({
    subject: document
      ? `Please sign: ${document.title}`
      : '',
    message: '',
    signing_mode: 'sequential',
    due_at: '',
    first_reminder_after_days: 2,
    reminder_interval_days: 2,
    escalation_days_before_due: 1,
  });
  const [recipients, setRecipients] = useState([
    newRecipient(),
  ]);
  const [error, setError] = useState('');

  const eligibleEmployees = useMemo(
    () => employees.filter((employee) => (
      !document
      || !isSuperAdmin
      || String(employee.tenant_id)
        === String(document.tenant_id)
    )),
    [document, employees, isSuperAdmin],
  );

  const selectedEmployeeIds = useMemo(
    () => new Set(
      recipients
        .map((recipient) => recipient.employee_id)
        .filter(Boolean),
    ),
    [recipients],
  );

  const updateRecipient = (index, changes) => {
    setRecipients((current) => current.map(
      (recipient, recipientIndex) => (
        recipientIndex === index
          ? { ...recipient, ...changes }
          : recipient
      ),
    ));
  };

  const addRecipient = () => {
    setRecipients((current) => [
      ...current,
      {
        ...newRecipient(),
        sequence: current.length + 1,
      },
    ]);
  };

  const removeRecipient = (index) => {
    setRecipients((current) => current.filter(
      (_, recipientIndex) => recipientIndex !== index,
    ));
  };

  const submit = (event) => {
    event.preventDefault();
    setError('');

    if (!document) {
      setError('Select a document before creating a request.');
      return;
    }

    if (recipients.some(
      (recipient) => !recipient.employee_id,
    )) {
      setError('Select an employee for every signatory.');
      return;
    }

    const dueAt = new Date(form.due_at);

    if (Number.isNaN(dueAt.getTime())) {
      setError('Enter a valid completion deadline.');
      return;
    }

    const payload = {
      document_id: document.id,
      subject: form.subject.trim(),
      message: form.message.trim() || null,
      signing_mode: form.signing_mode,
      due_at: dueAt.toISOString(),
      recipients: recipients.map((recipient, index) => ({
        employee_id: recipient.employee_id,
        role_label: (
          recipient.role_label.trim()
          || 'Signatory'
        ),
        sequence: form.signing_mode === 'parallel'
          ? 1
          : toInteger(recipient.sequence, index + 1),
      })),
      reminder: {
        first_reminder_after_days: toInteger(
          form.first_reminder_after_days,
          2,
        ),
        reminder_interval_days: toInteger(
          form.reminder_interval_days,
          2,
        ),
        escalation_days_before_due: (
          form.escalation_days_before_due === ''
            ? null
            : toInteger(
              form.escalation_days_before_due,
              1,
            )
        ),
        is_active: true,
      },
    };

    if (isSuperAdmin) {
      payload.tenant_id = document.tenant_id;
    }

    onSubmit(payload);
  };

  if (!document) return null;

  return (
    <form onSubmit={submit} className="space-y-6">
      <div className="rounded-2xl border border-cyan-100 bg-cyan-50 p-4">
        <p className="text-xs font-bold uppercase tracking-wider text-cyan-700">
          Selected document
        </p>
        <p className="mt-2 font-semibold text-slate-950">
          {document.title}
        </p>
        <p className="mt-1 text-xs text-slate-600">
          {document.original_filename}
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label="Email subject"
          value={form.subject}
          onChange={(event) => setForm({
            ...form,
            subject: event.target.value,
          })}
          required
        />

        <Input
          label="Completion deadline"
          type="datetime-local"
          value={form.due_at}
          onChange={(event) => setForm({
            ...form,
            due_at: event.target.value,
          })}
          required
        />
      </div>

      <label className="block space-y-1">
        <span className="text-sm font-medium text-slate-700">
          Message to signatories
        </span>
        <textarea
          aria-label="Message to signatories"
          rows={4}
          value={form.message}
          onChange={(event) => setForm({
            ...form,
            message: event.target.value,
          })}
          className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder="Explain what the recipient should review before signing."
        />
      </label>

      <label className="block space-y-1">
        <span className="text-sm font-medium text-slate-700">
          Signing order
        </span>
        <select
          aria-label="Signing order"
          value={form.signing_mode}
          onChange={(event) => setForm({
            ...form,
            signing_mode: event.target.value,
          })}
          className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
        >
          <option value="sequential">
            Sequential — notify one stage at a time
          </option>
          <option value="parallel">
            Parallel — notify all signatories together
          </option>
        </select>
      </label>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-semibold text-slate-950">
              Signatories
            </p>
            <p className="text-xs text-slate-500">
              Employees must have ACE platform access before
              they can receive a signing task.
            </p>
          </div>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={addRecipient}
          >
            <Plus size={15} />
            Add signatory
          </Button>
        </div>

        {recipients.map((recipient, index) => (
          <div
            key={`${index}-${recipient.employee_id}`}
            className="grid gap-3 rounded-2xl border border-slate-200 p-4 md:grid-cols-[1.4fr_1fr_120px_auto]"
          >
            <label className="block space-y-1">
              <span className="text-sm font-medium text-slate-700">
                Signatory {index + 1}
              </span>
              <select
                aria-label={`Signatory ${index + 1}`}
                value={recipient.employee_id}
                onChange={(event) => updateRecipient(
                  index,
                  { employee_id: event.target.value },
                )}
                required
                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
              >
                <option value="">Select employee</option>
                {eligibleEmployees.map((employee) => {
                  const selectedElsewhere = (
                    selectedEmployeeIds.has(employee.id)
                    && recipient.employee_id !== employee.id
                  );

                  return (
                    <option
                      key={employee.id}
                      value={employee.id}
                      disabled={selectedElsewhere}
                    >
                      {employee.full_name}
                      {employee.job_title
                        ? ` — ${employee.job_title}`
                        : ''}
                    </option>
                  );
                })}
              </select>
            </label>

            <Input
              label={`Role for signatory ${index + 1}`}
              value={recipient.role_label}
              onChange={(event) => updateRecipient(
                index,
                { role_label: event.target.value },
              )}
              placeholder="Employee, manager, witness"
            />

            <Input
              label="Sequence"
              type="number"
              min="1"
              value={
                form.signing_mode === 'parallel'
                  ? 1
                  : recipient.sequence
              }
              disabled={form.signing_mode === 'parallel'}
              onChange={(event) => updateRecipient(
                index,
                { sequence: event.target.value },
              )}
              required
            />

            <div className="flex items-end">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Remove signatory ${index + 1}`}
                disabled={recipients.length === 1}
                onClick={() => removeRecipient(index)}
              >
                <Trash2 size={16} />
              </Button>
            </div>
          </div>
        ))}
      </section>

      <section className="space-y-3">
        <div>
          <p className="font-semibold text-slate-950">
            Automated reminders
          </p>
          <p className="text-xs text-slate-500">
            Reminder delivery will stop automatically after the
            request is completed, declined, cancelled, or expired.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Input
            label="First reminder after days"
            type="number"
            min="0"
            value={form.first_reminder_after_days}
            onChange={(event) => setForm({
              ...form,
              first_reminder_after_days: event.target.value,
            })}
            required
          />

          <Input
            label="Repeat every days"
            type="number"
            min="1"
            value={form.reminder_interval_days}
            onChange={(event) => setForm({
              ...form,
              reminder_interval_days: event.target.value,
            })}
            required
          />

          <Input
            label="Escalate days before due"
            type="number"
            min="0"
            value={form.escalation_days_before_due}
            onChange={(event) => setForm({
              ...form,
              escalation_days_before_due: event.target.value,
            })}
          />
        </div>
      </section>

      <div className="flex justify-end">
        <Button
          type="submit"
          variant="accent"
          disabled={loading || eligibleEmployees.length === 0}
        >
          {loading
            ? 'Sending request...'
            : 'Send for signature'}
        </Button>
      </div>
    </form>
  );
}
