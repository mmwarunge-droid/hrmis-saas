import { useMemo, useState } from 'react';
import {
  BellRing,
  CalendarClock,
  CheckCircle2,
  CircleDashed,
  Clock3,
  FileSignature,
  History,
  RefreshCcw,
  UserRoundCheck,
  XCircle,
} from 'lucide-react';

import SignatureEvidencePanel from './SignatureEvidencePanel.jsx';
import SignatureSealPlacement from './SignatureSealPlacement.jsx';
import Badge from '../ui/Badge.jsx';
import Button from '../ui/Button.jsx';
import Card from '../ui/Card.jsx';
import EmptyState from '../ui/EmptyState.jsx';
import Input from '../ui/Input.jsx';

const ACTIVE_REQUEST_STATUSES = new Set([
  'sent',
  'in_progress',
]);
const RESENDABLE_REQUEST_STATUSES = new Set([
  'expired',
  'declined',
  'cancelled',
  'failed',
]);
const DEFAULT_RESEND_MESSAGE = (
  'We noticed that you have not yet signed this document. '
  + 'Please review it and complete your signature at your '
  + 'earliest convenience.'
);
const RESEND_DEADLINE_DAYS = 7;

function defaultResendDeadline() {
  return toDateTimeLocal(
    new Date(
      Date.now()
      + (RESEND_DEADLINE_DAYS * 24 * 60 * 60 * 1000),
    ),
  );
}

function formatDateTime(value) {
  if (!value) return '—';

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function toDateTimeLocal(value) {
  if (!value) return '';

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return '';
  }

  const offset = date.getTimezoneOffset() * 60000;

  return new Date(date.getTime() - offset)
    .toISOString()
    .slice(0, 16);
}

function statusTone(status) {
  if (status === 'completed' || status === 'signed') {
    return 'green';
  }

  if (status === 'declined' || status === 'cancelled') {
    return 'red';
  }

  if (
    status === 'sent'
    || status === 'in_progress'
    || status === 'notified'
    || status === 'viewed'
  ) {
    return 'amber';
  }

  return 'slate';
}

function eventLabel(eventType = '') {
  return eventType
    .replace(/^signature\./, '')
    .replaceAll('_', ' ');
}

export default function SignatureRequestDetails({
  request,
  loading = false,
  onRemind,
  onResend,
  onUpdateDeadline,
  onCancel,
  evidence = null,
  onRetryEvidence,
}) {
  const [deadline, setDeadline] = useState(
    () => toDateTimeLocal(request?.due_at),
  );
  const [showCancel, setShowCancel] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [showResend, setShowResend] = useState(false);
  const [resendDeadline, setResendDeadline] = useState(
    defaultResendDeadline,
  );
  const [resendMessage, setResendMessage] = useState(
    DEFAULT_RESEND_MESSAGE,
  );

  const recipients = useMemo(
    () => [...(request?.recipients || [])].sort(
      (left, right) => (
        left.sequence - right.sequence
      ),
    ),
    [request],
  );

  const events = useMemo(
    () => [...(request?.events || [])].sort(
      (left, right) => (
        new Date(right.occurred_at)
        - new Date(left.occurred_at)
      ),
    ),
    [request],
  );

  if (!request) return null;

  const isActive = ACTIVE_REQUEST_STATUSES.has(
    request.status,
  );
  const dueAt = request.due_at
    ? new Date(request.due_at)
    : null;
  const isOverdueInternal = Boolean(
    isActive
    && !request.provider
    && dueAt
    && !Number.isNaN(dueAt.getTime())
    && dueAt <= new Date(),
  );
  const canResend = (
    RESENDABLE_REQUEST_STATUSES.has(request.status)
    || isOverdueInternal
  );

  const recipientCount = (
    request.recipient_count
    ?? recipients.length
  );

  const signedCount = (
    request.signed_count
    ?? recipients.filter(
      (recipient) => recipient.status === 'signed',
    ).length
  );

  const progress = recipientCount
    ? Math.round((signedCount / recipientCount) * 100)
    : 0;

  const currentRecipients = recipients.filter(
    (recipient) => (
      recipient.sequence === request.current_sequence
      && ['notified', 'viewed'].includes(recipient.status)
    ),
  );

  const submitDeadline = (event) => {
    event.preventDefault();

    const parsed = new Date(deadline);

    if (Number.isNaN(parsed.getTime())) return;

    onUpdateDeadline(
      request.id,
      parsed.toISOString(),
    );
  };

  const submitCancel = (event) => {
    event.preventDefault();

    const reason = cancelReason.trim();

    if (!reason) return;

    onCancel(request.id, reason);
  };

  const submitResend = (event) => {
    event.preventDefault();

    const parsed = new Date(resendDeadline);
    const message = resendMessage.trim();

    if (Number.isNaN(parsed.getTime()) || !message) return;

    onResend(request.id, {
      due_at: parsed.toISOString(),
      message,
    });
  };

  return (
    <div className="space-y-6">
      <section className="rounded-xl bg-gradient-to-br from-slate-950 via-blue-950 to-blue-950 p-6 text-white">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex gap-4">
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-white/10 text-blue-200">
              <FileSignature size={22} />
            </span>

            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-xl font-bold">
                  {request.subject}
                </h3>

                <Badge tone={statusTone(request.status)}>
                  {request.status.replaceAll('_', ' ')}
                </Badge>

                {request.resend_attempt > 0 && (
                  <Badge tone="cyan">
                    Resend #{request.resend_attempt}
                  </Badge>
                )}
              </div>

              <p className="mt-2 text-sm text-slate-300">
                {request.document?.title || 'Document'}
              </p>

              {request.message && (
                <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
                  {request.message}
                </p>
              )}
            </div>
          </div>

          {isActive && !isOverdueInternal && (
            <Button
              type="button"
              variant="secondary"
              disabled={loading}
              onClick={() => onRemind(request.id)}
            >
              <BellRing size={16} />
              Send reminder now
            </Button>
          )}
        </div>

        <div className="mt-6">
          <div className="flex items-center justify-between text-xs font-semibold">
            <span>
              {signedCount} of {recipientCount} signed
            </span>
            <span>{progress}%</span>
          </div>

          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/15">
            <div
              className="h-full rounded-full bg-blue-300 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CalendarClock
            size={19}
            className="text-blue-700"
          />
          <p className="mt-3 text-xs font-bold uppercase tracking-wider text-slate-500">
            Deadline
          </p>
          <p className="mt-1 font-semibold text-slate-950">
            {formatDateTime(request.due_at)}
          </p>
        </Card>

        <Card>
          <UserRoundCheck
            size={19}
            className="text-blue-700"
          />
          <p className="mt-3 text-xs font-bold uppercase tracking-wider text-slate-500">
            Current signatory
          </p>
          <p className="mt-1 font-semibold text-slate-950">
            {currentRecipients.length
              ? currentRecipients
                .map((recipient) => recipient.name)
                .join(', ')
              : 'No active signatory'}
          </p>
        </Card>

        <Card>
          <Clock3
            size={19}
            className="text-amber-700"
          />
          <p className="mt-3 text-xs font-bold uppercase tracking-wider text-slate-500">
            Signing mode
          </p>
          <p className="mt-1 font-semibold capitalize text-slate-950">
            {request.signing_mode}
          </p>
        </Card>
      </div>

      {request.assurance_level === 'qes' && (
        <SignatureEvidencePanel
          requestId={request.id}
          evidence={evidence}
          loading={loading}
          onRetry={onRetryEvidence}
        />
      )}

      {request.seal_required && (
        <Card>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
                Finalization
              </p>
              <h3 className="mt-1 font-bold">
                Company seal
              </h3>
            </div>

            <Badge
              tone={
                request.seal_status === 'applied'
                  ? 'green'
                  : request.seal_status === 'pending'
                    ? 'amber'
                    : 'slate'
              }
            >
              {request.seal_status
                ? request.seal_status.replaceAll('_', ' ')
                : 'not available'}
            </Badge>
          </div>

          {request.seal_status === 'awaiting_signatures' && (
            <p className="mt-4 text-sm leading-6 text-slate-600">
              Waiting for all signatories to complete the request before
              the company seal can be applied.
            </p>
          )}

          {request.seal_status === 'pending' && (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
              <p className="font-semibold text-amber-950">
                Pending company seal
              </p>
              <p className="mt-1 text-sm leading-6 text-amber-900">
                Signing is complete. The company seal is ready for
                authorized review and placement.
              </p>
              <div className="mt-4">
                <SignatureSealPlacement
                  request={request}
                  seal={request.seal}
                  loading={loading}
                />
              </div>
            </div>
          )}

          {request.seal_status === 'applied' && (
            <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
              <p className="font-semibold text-emerald-950">
                Company seal applied
              </p>
              <p className="mt-1 text-sm text-emerald-900">
                Applied on {formatDateTime(request.sealed_at)}.
              </p>
            </div>
          )}
        </Card>
      )}

      {canResend && (
        <Card>
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="flex items-start gap-3">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-700">
                <RefreshCcw size={18} />
              </span>
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
                  Replacement request
                </p>
                <h3 className="font-bold">
                  Resend this document for signature
                </h3>
                <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
                  Kinetic will reuse this document, signing mode,
                  signatories and reminder settings. Recipient access
                  is revalidated before the new request is sent.
                </p>
              </div>
            </div>

            {!showResend && (
              <Button
                type="button"
                variant="secondary"
                disabled={loading}
                onClick={() => setShowResend(true)}
              >
                <RefreshCcw size={16} />
                Resend for signature
              </Button>
            )}
          </div>

          {showResend && (
            <form
              onSubmit={submitResend}
              className="mt-5 space-y-4 rounded-lg border border-blue-100 bg-blue-50/60 p-4"
            >
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Document
                  </p>
                  <p className="mt-1 font-semibold text-slate-950">
                    {request.document?.title || 'Document'}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Original deadline
                  </p>
                  <p className="mt-1 font-semibold text-slate-950">
                    {formatDateTime(request.due_at)}
                  </p>
                </div>
              </div>

              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Original recipients
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {recipients.map((recipient) => (
                    <Badge key={recipient.id} tone="slate">
                      {recipient.name} · {recipient.email}
                    </Badge>
                  ))}
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  If an employee email changed, Kinetic uses the
                  current active employee account when sending.
                </p>
              </div>

              <Input
                label="New signing deadline"
                type="datetime-local"
                value={resendDeadline}
                onChange={(event) => setResendDeadline(
                  event.target.value,
                )}
                required
              />

              <label className="block space-y-1">
                <span className="text-sm font-medium text-slate-700">
                  Resend message
                </span>
                <textarea
                  aria-label="Resend message"
                  rows={4}
                  value={resendMessage}
                  onChange={(event) => setResendMessage(
                    event.target.value,
                  )}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                  required
                />
              </label>

              <div className="flex flex-wrap justify-end gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={loading}
                  onClick={() => setShowResend(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={
                    loading
                    || !resendDeadline
                    || !resendMessage.trim()
                  }
                >
                  <RefreshCcw size={16} />
                  Resend for signature
                </Button>
              </div>
            </form>
          )}
        </Card>
      )}

      {isActive && !isOverdueInternal && (
        <Card>
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-lg bg-blue-50 text-blue-700">
              <CalendarClock size={18} />
            </span>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
                Follow-up
              </p>
              <h3 className="font-bold">
                Administrative controls
              </h3>
            </div>
          </div>

          <form
            onSubmit={submitDeadline}
            className="mt-5 flex flex-col gap-3 md:flex-row md:items-end"
          >
            <div className="flex-1">
              <Input
                label="New deadline"
                type="datetime-local"
                value={deadline}
                onChange={(event) => setDeadline(
                  event.target.value,
                )}
                required
              />
            </div>

            <Button
              type="submit"
              variant="secondary"
              disabled={loading || !deadline}
            >
              Update deadline
            </Button>

            <Button
              type="button"
              variant="danger"
              disabled={loading}
              onClick={() => setShowCancel(
                (current) => !current,
              )}
            >
              <XCircle size={16} />
              Cancel request
            </Button>
          </form>

          {showCancel && (
            <form
              onSubmit={submitCancel}
              className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4"
            >
              <label className="block space-y-1">
                <span className="text-sm font-medium text-red-800">
                  Reason for cancellation
                </span>
                <textarea
                  aria-label="Reason for cancellation"
                  rows={3}
                  value={cancelReason}
                  onChange={(event) => setCancelReason(
                    event.target.value,
                  )}
                  className="w-full rounded-lg border border-red-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-red-400 focus:ring-4 focus:ring-red-100"
                />
              </label>

              <div className="mt-3 flex justify-end">
                <Button
                  type="submit"
                  variant="danger"
                  size="sm"
                  disabled={
                    loading || !cancelReason.trim()
                  }
                >
                  Confirm cancellation
                </Button>
              </div>
            </form>
          )}
        </Card>
      )}

      <Card>
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-lg bg-blue-50 text-blue-700">
            <UserRoundCheck size={18} />
          </span>
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
              Routing
            </p>
            <h3 className="font-bold">Signatories</h3>
          </div>
        </div>

        <div className="mt-5 space-y-3">
          {recipients.map((recipient) => {
            const signed = recipient.status === 'signed';
            const current = (
              recipient.sequence === request.current_sequence
              && isActive
            );

            return (
              <div
                key={recipient.id}
                className="flex flex-col gap-4 rounded-lg border border-slate-100 p-4 md:flex-row md:items-center"
              >
                <span
                  className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${
                    signed
                      ? 'bg-emerald-50 text-emerald-700'
                      : current
                        ? 'bg-blue-50 text-blue-700'
                        : 'bg-slate-100 text-slate-500'
                  }`}
                >
                  {signed
                    ? <CheckCircle2 size={20} />
                    : <CircleDashed size={20} />}
                </span>

                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-slate-950">
                    {recipient.name}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {recipient.role_label || 'Signatory'}
                    {' · '}
                    Sequence {recipient.sequence}
                    {' · '}
                    {recipient.email}
                  </p>
                </div>

                {current && (
                  <Badge tone="cyan">
                    Current stage
                  </Badge>
                )}

                <Badge tone={statusTone(recipient.status)}>
                  {recipient.status.replaceAll('_', ' ')}
                </Badge>

                <p className="text-xs text-slate-500">
                  {recipient.signed_at
                    ? `Signed ${formatDateTime(recipient.signed_at)}`
                    : `Due ${formatDateTime(recipient.due_at)}`}
                </p>
              </div>
            );
          })}
        </div>
      </Card>

      <Card>
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-lg bg-slate-100 text-slate-700">
            <History size={18} />
          </span>
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Audit trail
            </p>
            <h3 className="font-bold">Activity timeline</h3>
          </div>
        </div>

        <div className="mt-5">
          {events.length === 0 ? (
            <EmptyState
              title="No activity recorded"
              description="Workflow events will appear here as recipients and administrators take action."
            />
          ) : (
            <ol className="space-y-4">
              {events.map((event) => (
                <li
                  key={event.id}
                  className="relative border-l-2 border-slate-100 pl-5"
                >
                  <span className="absolute -left-[7px] top-1 h-3 w-3 rounded-full border-2 border-white bg-blue-500" />

                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="font-semibold capitalize text-slate-900">
                        {event.description
                          || eventLabel(event.event_type)}
                      </p>
                      <p className="mt-1 text-xs capitalize text-slate-500">
                        {eventLabel(event.event_type)}
                      </p>
                    </div>

                    <time className="text-xs text-slate-500">
                      {formatDateTime(event.occurred_at)}
                    </time>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </Card>
    </div>
  );
}
