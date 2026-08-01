import { useState } from 'react';
import {
  ExternalLink,
  FileSignature,
  Send,
  ShieldCheck,
  XCircle,
} from 'lucide-react';

import { documentApi } from '../../api/documentApi';
import Badge from '../ui/Badge.jsx';
import Button from '../ui/Button.jsx';

function formatDeadline(value) {
  if (!value) return 'No deadline';

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

export default function SignatureTaskCard({
  task,
  loading = false,
  onViewed,
  onSign,
  onDecline,
}) {
  const [showDecline, setShowDecline] = useState(false);
  const [reason, setReason] = useState('');
  const externalQes = (
    task.external_signing_required
    && task.provider === 'dropbox_sign'
    && task.assurance_level === 'qes'
  );

  const submitDecline = () => {
    const normalizedReason = reason.trim();

    if (!normalizedReason) return;

    onDecline(task.id, normalizedReason);
  };

  return (
    <article className="rounded-lg border border-blue-100 bg-blue-50/40 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-blue-100 text-blue-800">
          <FileSignature size={20} />
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold text-slate-950">
              {task.subject}
            </p>
            <Badge tone="amber">
              {task.status.replaceAll('_', ' ')}
            </Badge>
            {externalQes && (
              <Badge tone="violet">
                QES target
              </Badge>
            )}
          </div>

          <p className="mt-1 text-sm text-slate-600">
            {task.document.title}
          </p>

          {task.message && (
            <p className="mt-2 text-xs leading-5 text-slate-500">
              {task.message}
            </p>
          )}

          <p className="mt-2 text-xs font-medium text-slate-500">
            Due {formatDeadline(task.due_at)}
          </p>

          {externalQes && (
            <div className="mt-3 flex gap-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-blue-950">
              <ShieldCheck
                className="mt-0.5 shrink-0"
                size={18}
              />
              <div>
                <p className="text-xs font-semibold">
                  Complete signing through Dropbox Sign
                </p>
                <p className="mt-1 text-xs leading-5 text-blue-800">
                  Use the provider-hosted invitation sent to your
                  email. Dropbox Sign controls identity verification,
                  consent, and signature evidence for this request.
                  Kinetic cannot confirm or decline it directly.
                </p>
                {task.provider_status && (
                  <p className="mt-1 text-xs font-medium text-blue-900">
                    Provider status:{' '}
                    {task.provider_status.replaceAll('_', ' ')}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <a
            href={documentApi.downloadUrl(task.document.id)}
            target="_blank"
            rel="noreferrer"
            onClick={externalQes
              ? undefined
              : () => onViewed(task.id)}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 transition hover:bg-slate-50"
          >
            <ExternalLink size={14} />
            {externalQes
              ? 'Review source document'
              : 'Review document'}
          </a>

          {!externalQes && (
            <>
              <Button
                type="button"
                size="sm"
                variant="accent"
                disabled={loading}
                onClick={() => onSign(task.id)}
              >
                <Send size={14} />
                Confirm signature
              </Button>

              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={loading}
                onClick={() => setShowDecline(
                  (current) => !current,
                )}
              >
                <XCircle size={14} />
                Decline
              </Button>
            </>
          )}
        </div>
      </div>

      {showDecline && !externalQes && (
        <div className="mt-4 border-t border-blue-100 pt-4">
          <label className="block space-y-1">
            <span className="text-sm font-medium text-slate-700">
              Reason for declining
            </span>
            <textarea
              aria-label="Reason for declining"
              rows={3}
              value={reason}
              onChange={(event) => setReason(
                event.target.value,
              )}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
            />
          </label>

          <div className="mt-3 flex justify-end">
            <Button
              type="button"
              variant="danger"
              size="sm"
              disabled={loading || !reason.trim()}
              onClick={submitDecline}
            >
              Submit decline
            </Button>
          </div>
        </div>
      )}
    </article>
  );
}
