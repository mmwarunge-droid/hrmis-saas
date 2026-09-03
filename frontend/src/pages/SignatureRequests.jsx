import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  CheckCircle2,
  Clock3,
  FileSignature,
  Search,
  TriangleAlert,
} from 'lucide-react';

import { signatureApi } from '../api/signatureApi';
import SignatureRequestDetails from '../components/documents/SignatureRequestDetails.jsx';
import Alert from '../components/ui/Alert.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import Input from '../components/ui/Input.jsx';
import Modal from '../components/ui/Modal.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import Table from '../components/ui/Table.jsx';

const ACTIVE_STATUSES = new Set([
  'sent',
  'in_progress',
]);

function statusTone(status) {
  if (status === 'completed') return 'green';

  if (
    status === 'declined'
    || status === 'cancelled'
    || status === 'expired'
  ) {
    return 'red';
  }

  if (
    status === 'sent'
    || status === 'in_progress'
  ) {
    return 'amber';
  }

  return 'slate';
}

function formatDate(value) {
  if (!value) return '—';

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function isOverdue(request) {
  if (!ACTIVE_STATUSES.has(request.status)) {
    return false;
  }

  const deadline = new Date(request.due_at);

  return (
    !Number.isNaN(deadline.getTime())
    && deadline < new Date()
  );
}

function currentSignatories(request) {
  const recipients = request.recipients || [];

  return recipients.filter((recipient) => (
    recipient.sequence === request.current_sequence
    && ['notified', 'viewed'].includes(recipient.status)
  ));
}

export default function SignatureRequests() {
  const [searchParams] = useSearchParams();
  const documentId = searchParams.get('document_id') || '';
  const [requests, setRequests] = useState([]);
  const [details, setDetails] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(async () => {
    setLoading(true);

    try {
      const params = {};

      if (status !== 'all') {
        params.status = status;
      }

      if (documentId) {
        params.document_id = documentId;
      }

      const response = await signatureApi.list(params);

      setRequests(response.data.items || []);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to load signature requests',
      );
    } finally {
      setLoading(false);
    }
  }, [documentId, status]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(
    () => requests.filter((request) => {
      if (!query) return true;

      const searchable = [
        request.subject,
        request.document?.title,
        request.document?.original_filename,
        ...(request.recipients || []).flatMap(
          (recipient) => [
            recipient.name,
            recipient.email,
          ],
        ),
      ].join(' ').toLowerCase();

      return searchable.includes(query.toLowerCase());
    }),
    [query, requests],
  );

  const active = requests.filter(
    (request) => ACTIVE_STATUSES.has(request.status),
  ).length;

  const completed = requests.filter(
    (request) => request.status === 'completed',
  ).length;

  const overdue = requests.filter(isOverdue).length;

  const openDetails = async (request) => {
    setDetailsOpen(true);
    setDetails(null);
    setError('');

    try {
      const [
        requestResponse,
        evidenceResponse,
      ] = await Promise.all([
        signatureApi.get(request.id),
        request.assurance_level === 'qes'
          ? signatureApi.evidence(request.id)
          : Promise.resolve({ data: null }),
      ]);

      setDetails(requestResponse.data);
      setEvidence(evidenceResponse.data);
    } catch (err) {
      setDetailsOpen(false);
      setError(
        err.error?.message
        || 'Unable to load signature request details',
      );
    }
  };

  const refreshDetails = async (requestId) => {
    const response = await signatureApi.get(requestId);
    setDetails(response.data);

    if (response.data.assurance_level === 'qes') {
      const evidenceResponse = await signatureApi.evidence(
        requestId,
      );
      setEvidence(evidenceResponse.data);
    }

    await load();
  };

  const remind = async (requestId) => {
    setActionLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await signatureApi.remind(requestId);
      const count = response.data.recipient_count;

      setSuccess(
        `Reminder sent to ${count} active signator`
        + `${count === 1 ? 'y' : 'ies'}.`,
      );

      await refreshDetails(requestId);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to send signing reminder',
      );
    } finally {
      setActionLoading(false);
    }
  };

  const resend = async (requestId, payload) => {
    setActionLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await signatureApi.resend(
        requestId,
        payload,
      );

      setSuccess('Signature request resent successfully.');
      setDetails(response.data);
      await load();
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to resend signature request',
      );
    } finally {
      setActionLoading(false);
    }
  };

  const updateDeadline = async (requestId, dueAt) => {
    setActionLoading(true);
    setError('');
    setSuccess('');

    try {
      await signatureApi.updateDeadline(
        requestId,
        dueAt,
      );

      setSuccess('Signature deadline updated.');
      await refreshDetails(requestId);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to update signature deadline',
      );
    } finally {
      setActionLoading(false);
    }
  };

  const cancel = async (requestId, reason) => {
    setActionLoading(true);
    setError('');
    setSuccess('');

    try {
      await signatureApi.cancel(requestId, reason);

      setSuccess('Signature request cancelled.');
      await refreshDetails(requestId);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to cancel signature request',
      );
    } finally {
      setActionLoading(false);
    }
  };

  const applySeal = async (requestId) => {
    setActionLoading(true);
    setError('');
    setSuccess('');

    try {
      await signatureApi.applySeal(requestId);
      setSuccess('Company seal applied successfully.');
      await refreshDetails(requestId);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to apply company seal',
      );
    } finally {
      setActionLoading(false);
    }
  };

  const retryEvidence = async (requestId) => {
    setActionLoading(true);
    setError('');
    setSuccess('');

    try {
      await signatureApi.retryEvidence(requestId);
      setSuccess('Signature evidence retry queued.');
      await refreshDetails(requestId);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to retry signature evidence',
      );
    } finally {
      setActionLoading(false);
    }
  };

  const columns = [
    {
      key: 'subject',
      label: 'Request',
      render: (request) => (
        <div>
          <p className="font-semibold text-slate-950">
            {request.subject}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {request.document?.title || 'Document'}
          </p>
        </div>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      render: (request) => (
        <div className="flex flex-wrap gap-2">
          <Badge tone={statusTone(request.status)}>
            {request.status.replaceAll('_', ' ')}
          </Badge>

          {isOverdue(request) && (
            <Badge tone="red">Overdue</Badge>
          )}
        </div>
      ),
    },
    {
      key: 'progress',
      label: 'Progress',
      render: (request) => (
        <div className="min-w-32">
          <p className="text-xs font-semibold text-slate-700">
            {request.signed_count} of{' '}
            {request.recipient_count} signed
          </p>

          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-blue-600"
              style={{
                width: `${
                  request.recipient_count
                    ? Math.round(
                      (
                        request.signed_count
                        / request.recipient_count
                      ) * 100,
                    )
                    : 0
                }%`,
              }}
            />
          </div>
        </div>
      ),
    },
    {
      key: 'current',
      label: 'Current signatory',
      render: (request) => {
        const current = currentSignatories(request);

        return current.length
          ? current.map(
            (recipient) => recipient.name,
          ).join(', ')
          : '—';
      },
    },
    {
      key: 'due_at',
      label: 'Due',
      render: (request) => formatDate(request.due_at),
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (request) => (
        <Button
          type="button"
          size="sm"
          variant="soft"
          onClick={(event) => {
            event.stopPropagation();
            openDetails(request);
          }}
        >
          View details
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Docs"
        title="Signature requests"
        description="Track recipient progress, deadlines, reminders and timestamped activity across document-signing workflows."
      />

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard
          label="Requests"
          value={requests.length}
          detail="Requests in the current view"
          icon={FileSignature}
          tone="blue"
        />
        <StatCard
          label="Active"
          value={active}
          detail="Waiting for one or more signatories"
          icon={Clock3}
          tone="violet"
        />
        <StatCard
          label="Completed"
          value={completed}
          detail="All recipients signed"
          icon={CheckCircle2}
          tone="emerald"
        />
        <StatCard
          label="Overdue"
          value={overdue}
          detail="Active requests past deadline"
          icon={TriangleAlert}
          tone="rose"
        />
      </div>

      <Card>
        <div className="grid gap-4 md:grid-cols-[1fr_220px]">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-3 text-slate-400"
              size={18}
            />
            <Input
              className="pl-10"
              placeholder="Search documents, subjects or signatories"
              value={query}
              onChange={(event) => setQuery(
                event.target.value,
              )}
            />
          </div>

          <select
            aria-label="Request status"
            value={status}
            onChange={(event) => setStatus(
              event.target.value,
            )}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
          >
            <option value="all">All statuses</option>
            <option value="sent">Sent</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
            <option value="declined">Declined</option>
            <option value="cancelled">Cancelled</option>
            <option value="expired">Expired</option>
          </select>
        </div>
      </Card>

      {loading ? (
        <Card>
          <p className="text-sm text-slate-500">
            Loading signature requests...
          </p>
        </Card>
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No signature requests found"
          description="Send a document for signature or change the current search and status filters."
        />
      ) : (
        <Table
          columns={columns}
          rows={filtered}
          onRowClick={openDetails}
        />
      )}

      <Modal
        title="Signature request details"
        open={detailsOpen}
        onClose={() => {
          if (actionLoading) return;
          setDetailsOpen(false);
          setDetails(null);
          setEvidence(null);
        }}
        size="xl"
      >
        {details ? (
          <SignatureRequestDetails
            key={`${details.id}:${details.due_at}:${details.status}`}
            request={details}
            loading={actionLoading}
            onRemind={remind}
            onResend={resend}
            onUpdateDeadline={updateDeadline}
            onCancel={cancel}
            onApplySeal={applySeal}
            evidence={evidence}
            onRetryEvidence={retryEvidence}
          />
        ) : (
          <p className="py-12 text-center text-sm text-slate-500">
            Loading request details...
          </p>
        )}
      </Modal>
    </div>
  );
}
