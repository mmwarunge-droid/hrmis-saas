import {
  Archive,
  CheckCircle2,
  Download,
  FileCheck2,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';

import { signatureApi } from '../../api/signatureApi';
import Badge from '../ui/Badge.jsx';
import Button from '../ui/Button.jsx';
import Card from '../ui/Card.jsx';

function tone(status) {
  if (status === 'verified') return 'green';
  if (status === 'failed') return 'red';

  if (
    status === 'pending'
    || status === 'processing'
    || status === 'retry_scheduled'
  ) {
    return 'amber';
  }

  return 'slate';
}

function label(value = '') {
  return value.replaceAll('_', ' ');
}

function formatDateTime(value) {
  if (!value) return '—';

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
}

function artifactLabel(type) {
  const labels = {
    original_document: 'Original source document',
    signed_document: 'Final signed PDF',
    audit_trail: 'Provider audit trail',
    completion_certificate: 'Completion certificate',
  };

  return labels[type] || label(type);
}

export default function SignatureEvidencePanel({
  requestId,
  evidence,
  loading = false,
  onRetry,
}) {
  if (!evidence) {
    return (
      <Card>
        <p className="text-sm text-slate-500">
          Loading qualified-signature evidence...
        </p>
      </Card>
    );
  }

  const retryable = [
    'failed',
    'retry_scheduled',
  ].includes(evidence.evidence_status);

  return (
    <Card>
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-emerald-50 text-emerald-700">
            <FileCheck2 size={18} />
          </span>

          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">
              QES evidence
            </p>
            <h3 className="font-bold">
              Signed-file evidence package
            </h3>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge tone={tone(evidence.evidence_status)}>
                {label(evidence.evidence_status)}
              </Badge>
              <span className="text-xs text-slate-500">
                {evidence.evidence_attempts} ingestion attempt
                {evidence.evidence_attempts === 1 ? '' : 's'}
              </span>
            </div>
          </div>
        </div>

        {retryable && (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={loading}
            onClick={() => onRetry(requestId)}
          >
            <RefreshCw size={15} />
            Retry evidence
          </Button>
        )}
      </div>

      {evidence.evidence_last_error && (
        <div className="mt-5 flex gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <ShieldAlert size={18} className="shrink-0" />
          <p>{evidence.evidence_last_error}</p>
        </div>
      )}

      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <div className="rounded-lg bg-slate-50 p-4">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Provider
          </p>
          <p className="mt-1 font-semibold capitalize text-slate-950">
            {label(evidence.provider || '—')}
          </p>
        </div>
        <div className="rounded-lg bg-slate-50 p-4">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Last attempt
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-950">
            {formatDateTime(evidence.evidence_last_attempt_at)}
          </p>
        </div>
        <div className="rounded-lg bg-slate-50 p-4">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Verified
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-950">
            {formatDateTime(evidence.evidence_completed_at)}
          </p>
        </div>
      </div>

      {evidence.artifacts?.length > 0 && (
        <div className="mt-5 space-y-3">
          {evidence.artifacts.map((artifact) => (
            <div
              key={artifact.id}
              className="flex flex-col gap-3 rounded-lg border border-slate-100 p-4 md:flex-row md:items-center"
            >
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-700">
                <Archive size={17} />
              </span>

              <div className="min-w-0 flex-1">
                <p className="font-semibold text-slate-950">
                  {artifactLabel(artifact.artifact_type)}
                </p>
                <p className="mt-1 truncate font-mono text-xs text-slate-500">
                  SHA-256 {artifact.checksum_sha256}
                </p>
              </div>

              <a
                href={signatureApi.artifactDownloadUrl(
                  requestId,
                  artifact.id,
                )}
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 transition hover:bg-slate-50"
              >
                <Download size={14} />
                Download
              </a>
            </div>
          ))}
        </div>
      )}

      {evidence.evidence_status === 'verified' && (
        <div className="mt-5 flex gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          <CheckCircle2 size={18} className="shrink-0" />
          <p>
            Kinetic verified the provider request mapping, callback,
            signed-file hashes, and audit-trail hashes. This
            operational check does not independently determine
            legal recognition or certification status.
          </p>
        </div>
      )}
    </Card>
  );
}
