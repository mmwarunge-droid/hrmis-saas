import Form from '../forms/Form.jsx';
import { useMemo, useState } from 'react';
import {
  Plus,
  ShieldCheck,
  Trash2,
} from 'lucide-react';

import { signatureApi } from '../../api/signatureApi.js';
import SignatureFieldPlacement from './SignatureFieldPlacement.jsx';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';
import Select from '../ui/Select.jsx';

const DAY_MS = 86400000;
const MAX_STANDARD_SIGNATORIES = 4;

function newRecipient() {
  return {
    employee_id: '',
    role_label: 'Signatory',
    sequence: 1,
    fields: [],
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
  template = null,
}) {
  const [form, setForm] = useState({
    subject: document
      ? `Please sign: ${document.title}`
      : '',
    message: '',
    assurance_level: 'standard',
    signing_mode: 'sequential',
    seal_required: false,
    due_date: '',
    due_time: '',
    first_reminder_after_days: 2,
    reminder_interval_days: 2,
    escalation_days_before_due: 1,
    ...(template?.definition ? { subject: template.definition.subject, message: template.definition.message, signing_mode: template.definition.signing_mode } : {}),
  });
  const [recipients, setRecipients] = useState(() => template?.definition?.recipients?.map((role, index) => ({
    ...newRecipient(), ...role, employee_id: index === (template.definition.employee_role_index || 0) ? document?.employee_id || '' : '',
  })) || [newRecipient()]);
  const [templateName, setTemplateName] = useState('');
  const [employeeRoleIndex, setEmployeeRoleIndex] = useState(template?.definition?.employee_role_index || 0);
  const [templateSaved, setTemplateSaved] = useState('');
  const [templateSaving, setTemplateSaving] = useState(false);
  const [filingEmployee, setFilingEmployee] = useState(document?.employee_id || '');
  const saveTemplate = async () => {
    setTemplateSaving(true); setError(''); setTemplateSaved('');
    try {
      await signatureApi.saveTemplate({ name: templateName.trim(), document_id: document.id,
        ...(isSuperAdmin ? { tenant_id: document.tenant_id } : {}),
        definition: { subject: form.subject, message: form.message, signing_mode: form.signing_mode,
          field_placement_mode: fieldPlacementMode,
          employee_role_index: employeeRoleIndex,
          recipients: recipients.map(({ role_label, sequence, fields }) => ({ role_label, sequence: Number(sequence), fields })),
        },
      });
      setTemplateSaved('Template saved. It is available in the document library.');
    } catch (err) { setError(err.error?.message || 'Unable to save template.'); }
    finally { setTemplateSaving(false); }
  };
  const [error, setError] = useState('');
  const [fieldPlacementMode, setFieldPlacementMode] = useState(template?.definition?.field_placement_mode || 'document');

  const isQes = form.assurance_level === 'qes';

  const documentFilename = (
    document?.original_filename?.toLowerCase() || ''
  );
  const documentMimeType = (
    document?.mime_type?.toLowerCase() || ''
  );

  const isPdfDocument = (
    documentMimeType === 'application/pdf'
    || documentFilename.endsWith('.pdf')
  );

  const isDocxDocument = (
    documentMimeType === (
      'application/vnd.openxmlformats-officedocument.'
      + 'wordprocessingml.document'
    )
    || documentFilename.endsWith('.docx')
  );

  const isStandardSigningDocument = (
    isPdfDocument || isDocxDocument
  );

  const usesDocumentFields = (
    !isQes
    && isPdfDocument
    && !isDocxDocument
    && fieldPlacementMode === 'document'
  );

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

  const updateAssurance = (assuranceLevel) => {
    setForm((current) => ({
      ...current,
      assurance_level: assuranceLevel,
      signing_mode: assuranceLevel === 'qes'
        ? 'sequential'
        : current.signing_mode,
    }));

    if (assuranceLevel === 'qes') {
      setRecipients((current) => [
        current[0] || newRecipient(),
      ]);
    }
  };

  const addRecipient = () => {
    setRecipients((current) => {
      if (
        current.length
        >= MAX_STANDARD_SIGNATORIES
      ) {
        return current;
      }

      return [
        ...current,
        {
          ...newRecipient(),
          sequence: current.length + 1,
        },
      ];
    });
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

    if (
      !isQes
      && recipients.length
        > MAX_STANDARD_SIGNATORIES
    ) {
      setError(
        'Standard signing supports up to four signatories.',
      );
      return;
    }

    if (recipients.some(
      (recipient) => !recipient.employee_id,
    )) {
      setError('Select an employee for every signatory.');
      return;
    }

    if (!isQes && !isStandardSigningDocument) {
      setError(
        'Standard Kinetic signing supports PDF and Word (.docx) documents only.',
      );
      return;
    }

    if (isQes && recipients.length !== 1) {
      setError('Qualified eID signing requires one signatory.');
      return;
    }

    if (usesDocumentFields) {
      const incompleteSigner = recipients.findIndex((recipient) => {
        const fieldTypes = new Set((recipient.fields || []).map((field) => field.field_type));
        return !fieldTypes.has('signature') || !fieldTypes.has('date');
      });
      if (incompleteSigner >= 0) {
        setError(`Place both a signature and date field for signatory ${incompleteSigner + 1}.`);
        return;
      }
    }

    const dueAt = new Date(
      `${form.due_date}T${form.due_time}`,
    );

    if (Number.isNaN(dueAt.getTime())) {
      setError('Enter a valid completion deadline.');
      return;
    }

    if (dueAt <= new Date()) {
      setError('The completion deadline must be in the future.');
      return;
    }

    if (isQes) {
      const minimum = Date.now() + DAY_MS;
      const maximum = Date.now() + (90 * DAY_MS);

      if (
        dueAt.getTime() < minimum
        || dueAt.getTime() > maximum
      ) {
        setError(
          'Qualified eID signing requires a deadline '
          + 'between 1 and 90 days from now.',
        );
        return;
      }
    }

    const signingMode = isQes
      ? 'sequential'
      : form.signing_mode;
    const payload = {
      document_id: document.id,
      save_as_draft: false,
      ...(filingEmployee ? { filing_employee_id: filingEmployee } : {}),
      subject: form.subject.trim(),
      message: form.message.trim() || null,
      assurance_level: form.assurance_level,
      signing_mode: signingMode,
      seal_required: form.seal_required,
      due_at: dueAt.toISOString(),
      recipients: recipients.map((recipient, index) => ({
        employee_id: recipient.employee_id,
        role_label: (
          recipient.role_label.trim()
          || 'Signatory'
        ),
        sequence: signingMode === 'parallel'
          ? 1
          : toInteger(recipient.sequence, index + 1),
        ...(usesDocumentFields
          ? { fields: recipient.fields || [] }
          : {}),
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

    return onSubmit(payload);
  };

  if (!document) return null;

  return (
    <Form error={error} draft={{ key: `signing.${document.id}`, title: `Signing: ${document.title}`,
      data: { documentId: document.id, form, recipients, filingEmployee, fieldPlacementMode, templateName, employeeRoleIndex },
      onRestore: (saved) => {
        if (saved.documentId !== document.id) return;
        setForm(saved.form); setRecipients(saved.recipients); setFilingEmployee(saved.filingEmployee);
        setFieldPlacementMode(saved.fieldPlacementMode); setTemplateName(saved.templateName || '');
        setEmployeeRoleIndex(saved.employeeRoleIndex || 0); setError('');
      },
    }} onSubmit={submit} className="space-y-6">
      <div className="rounded-lg border border-blue-100 bg-blue-50 p-4">
        <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
          Selected document
        </p>
        <p className="mt-2 font-semibold text-slate-950">
          {document.title}
        </p>
        <p className="mt-1 text-xs text-slate-600">
          {document.original_filename}
        </p>
      </div>


      <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 bg-white p-4">
        <input
          type="checkbox"
          aria-label="Require company seal after signing"
          checked={form.seal_required}
          onChange={(event) => setForm((current) => ({
            ...current,
            seal_required: event.target.checked,
          }))}
          className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-700"
        />
        <span>
          <span className="block text-sm font-semibold text-slate-950">
            Require company seal after signing
          </span>
          <span className="mt-1 block text-xs leading-5 text-slate-500">
            After all signatories complete, an authorized reviewer must place and apply the company seal.
          </span>
        </span>
      </label>

      <Select
        label="Signature assurance"
        value={form.assurance_level}
        onChange={(event) => updateAssurance(
          event.target.value,
        )}
      >
        <option value="qes">
          Qualified electronic signature target — eID
        </option>
        <option value="standard">
          Standard Kinetic electronic signature
        </option>
      </Select>

      {isQes && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-blue-950">
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-0.5 shrink-0" size={19} />
            <div>
              <p className="text-sm font-semibold">
                Identity-verified provider signing
              </p>
              <p className="mt-1 text-xs leading-5 text-blue-800">
                Dropbox Sign will email one signatory and require
                an eID signing ceremony. Kinetic will treat QES as a
                target until the signed PDF and provider evidence
                are captured and verified.
              </p>
              <p className="mt-2 text-xs font-medium text-blue-900">
                The deadline must be 1–90 days ahead and is
                rounded down to the nearest UTC hour by the
                provider.
              </p>
            </div>
          </div>
        </div>
      )}

      {!isQes && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-emerald-950">
          <p className="text-sm font-semibold">
            Standard Kinetic signing
          </p>
          <p className="mt-1 text-xs leading-5 text-emerald-800">
            {isDocxDocument
              ? (
                'Kinetic converts this Word document once to an '
                + 'immutable PDF signing snapshot. Word documents '
                + 'use the signing-record page for signature and '
                + 'server-controlled signing date fields.'
              )
              : (
                "Kinetic generates each signature from the signatory's "
                + 'official profile name and stamps the signing date '
                + 'from the server. For PDF contracts and forms, prepare '
                + 'signing fields directly on the original document. '
                + 'The legacy signing-record page remains available '
                + 'for simple workflows.'
              )}
          </p>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            <label className={`cursor-pointer rounded-lg border p-3 ${fieldPlacementMode === 'record' ? 'border-emerald-500 bg-white' : 'border-emerald-200 bg-emerald-50'}`}>
              <span className="flex items-start gap-2">
                <input
                  type="radio"
                  name="field-placement-mode"
                  value="record"
                  checked={
                    isDocxDocument
                    || fieldPlacementMode === 'record'
                  }
                  onChange={() => setFieldPlacementMode('record')}
                  className="mt-0.5"
                />
                <span>
                  <strong className="block text-xs">Legacy signing record page</strong>
                  <span className="mt-0.5 block text-[11px] leading-4 text-emerald-800">Use when a separate signing record is preferred instead of placing fields on the source PDF.</span>
                </span>
              </span>
            </label>
            <label className={`${isDocxDocument ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'} rounded-lg border p-3 ${fieldPlacementMode === 'document' && !isDocxDocument ? 'border-emerald-500 bg-white' : 'border-emerald-200 bg-emerald-50'}`}>
              <span className="flex items-start gap-2">
                <input
                  type="radio"
                  name="field-placement-mode"
                  value="document"
                  checked={
                    !isDocxDocument
                    && fieldPlacementMode === 'document'
                  }
                  disabled={isDocxDocument}
                  onChange={() => setFieldPlacementMode('document')}
                  className="mt-0.5"
                />
                <span>
                  <strong className="block text-xs">Prepare fields on PDF</strong>
                  <span className="mt-0.5 block text-[11px] leading-4 text-emerald-800">
                    {isDocxDocument
                      ? 'Available for PDF source documents only.'
                      : 'Place signature, date, name, text and initials directly on the original PDF.'}
                  </span>
                </span>
              </span>
            </label>
          </div>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label="Email subject" name="subject"
          value={form.subject}
          onChange={(event) => setForm({
            ...form,
            subject: event.target.value,
          })}
          required
        />

        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label="Completion date" name="due_date"
            type="date"
            value={form.due_date}
            onChange={(event) => setForm({
              ...form,
              due_date: event.target.value,
            })}
            required
          />

          <Input
            label="Deadline time" name="due_time"
            type="time"
            value={form.due_time}
            onChange={(event) => setForm({
              ...form,
              due_time: event.target.value,
            })}
            required
          />
        </div>
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
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
          placeholder="Explain what the recipient should review before signing."
        />
      </label>

      <Select
        label="Signing order"
        value={isQes ? 'sequential' : form.signing_mode}
        disabled={isQes}
        onChange={(event) => setForm({
          ...form,
          signing_mode: event.target.value,
        })}
      >
        <option value="sequential">
          Sequential — notify one stage at a time
        </option>
        <option value="parallel">
          Parallel — notify all signatories together
        </option>
      </Select>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-semibold text-slate-950">
              Signatories
            </p>
            <p className="text-xs text-slate-500">
              {isQes
                ? 'Qualified eID signing supports exactly one employee.'
                : 'Employees must have Kinetic platform access before they can receive a signing task.'}
            </p>
          </div>

          {!isQes && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={addRecipient}
              disabled={
                recipients.length
                >= MAX_STANDARD_SIGNATORIES
              }
            >
              <Plus size={15} />
              Add signatory
            </Button>
          )}
        </div>

        {recipients.map((recipient, index) => (
          <div
            key={`${index}-${recipient.employee_id}`}
            className="grid gap-3 rounded-lg border border-slate-200 p-4 md:grid-cols-[1.4fr_1fr_120px_auto]"
          >
            <Select
              label={`Signatory ${index + 1}`}
              name={`recipients.${index}.employee_id`}
              value={recipient.employee_id}
                onChange={(event) => updateRecipient(
                  index,
                  { employee_id: event.target.value },
                )}
                required
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
            </Select>

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
                isQes || form.signing_mode === 'parallel'
                  ? 1
                  : recipient.sequence
              }
              disabled={
                isQes || form.signing_mode === 'parallel'
              }
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
                disabled={isQes || recipients.length === 1}
                onClick={() => removeRecipient(index)}
              >
                <Trash2 size={16} />
              </Button>
            </div>
          </div>
        ))}
      </section>

      {usesDocumentFields && (
        <SignatureFieldPlacement
          documentId={document.id}
          recipients={recipients}
          employees={eligibleEmployees}
          onFieldsChange={(index, fields) => updateRecipient(index, { fields })}
        />
      )}

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

      {!isQes && <section className="space-y-3 rounded-lg border p-4">
        <Select
          label="Store executed copy in employee file"
          aria-label="Employee file"
          value={filingEmployee}
          onChange={(event) => setFilingEmployee(event.target.value)}
          required
        >
          <option value="">Select employee</option>
          {eligibleEmployees.map((employee) => <option key={employee.id} value={employee.id}>{employee.full_name}</option>)}
        </Select>
        <Select
          label="Employee role when reusing this template"
          aria-label="Template employee role"
          value={employeeRoleIndex}
          onChange={(event) => setEmployeeRoleIndex(Number(event.target.value))}
        >
          {recipients.map((recipient, index) => <option key={index} value={index}>{recipient.role_label || 'Signatory'} ({index + 1})</option>)}
        </Select>
        <Input label="Template name" value={templateName} onChange={(event) => setTemplateName(event.target.value)} placeholder="Employment Contract - Kenya" />
        <Button type="button" variant="secondary" disabled={templateSaving || templateName.trim().length < 2} onClick={saveTemplate}>Save as template</Button>
        {templateSaved && <p role="status" className="text-sm text-green-700">{templateSaved}</p>}
      </section>}
      <div className="flex justify-end gap-3">
        <Button
          type="submit"
          variant="accent"
          disabled={loading || eligibleEmployees.length === 0}
        >
          {loading
            ? 'Sending request...'
            : isQes
              ? 'Send qualified-signature request'
              : 'Send for signature'}
        </Button>
      </div>
    </Form>
  );
}
