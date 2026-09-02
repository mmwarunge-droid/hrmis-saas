import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  CalendarDays,
  Check,
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileCheck2,
  Send,
  ShieldCheck,
  UserRoundCheck,
  XCircle,
} from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { documentApi } from '../api/documentApi.js';
import { signatureApi } from '../api/signatureApi.js';
import PdfSigningViewer from '../components/documents/PdfSigningViewer.jsx';
import SignatureDiscussionPanel from '../components/signatures/SignatureDiscussionPanel.jsx';
import Alert from '../components/ui/Alert.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';

const HANDWRITTEN_SIGNATURE_STYLE = {
  fontFamily: [
    '"Palace Script MT"',
    '"Brush Script MT"',
    '"URW Chancery L"',
    '"Apple Chancery"',
    'cursive',
  ].join(', '),
  fontWeight: 400,
  letterSpacing: 0,
};


function formatDate(value) {
  if (!value) return 'Not set';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function formatDay(value) {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return 'Set on submission';
  return date.toLocaleDateString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function statusTone(status) {
  if (status === 'signed') return 'green';
  if (status === 'declined' || status === 'expired') return 'red';
  if (status === 'viewed' || status === 'notified') return 'amber';
  return 'slate';
}

function Step({ complete, active, number, title, description }) {
  return (
    <div className="flex gap-3">
      <div className={`grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-bold ${complete ? 'bg-emerald-600 text-white' : active ? 'bg-blue-700 text-white' : 'bg-slate-100 text-slate-500'}`}>
        {complete ? <Check size={15} /> : number}
      </div>
      <div>
        <p className="text-sm font-semibold text-slate-900">{title}</p>
        <p className="mt-0.5 text-xs leading-5 text-slate-500">{description}</p>
      </div>
    </div>
  );
}

export default function SignatureTask() {
  const { recipientId } = useParams();
  const [task, setTask] = useState(null);
  const [documentUrl, setDocumentUrl] = useState(null);
  const [documentRefreshKey, setDocumentRefreshKey] = useState(0);
  const [declineReason, setDeclineReason] = useState('');
  const [showDecline, setShowDecline] = useState(false);
  const [consent, setConsent] = useState(false);
  const [signatureStyle, setSignatureStyle] = useState('calligraphy_1');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const closed = useMemo(
    () => ['signed', 'declined', 'expired', 'skipped'].includes(task?.status),
    [task?.status],
  );

  const currentFields = useMemo(
    () => (task?.fields || []).filter((field) => (
      field.is_current_recipient && !field.completed_at
    )),
    [task?.fields],
  );

  const load = useCallback(async () => {
    const taskResponse = await signatureApi.recipient(recipientId);
    setTask(taskResponse.data);
  }, [recipientId]);

  useEffect(() => {
    load().catch((err) => setError(
      err.error?.message || 'Unable to load signature task.',
    ));
  }, [load]);

  useEffect(() => {
    let active = true;
    if (!task?.document?.id) return undefined;

    setDocumentUrl(null);

    const request = task.external_signing_required
      ? documentApi.content(task.document.id)
      : signatureApi.signingDocument(recipientId);

    request
      .then(async (blob) => {
        const documentData = new Uint8Array(
          await blob.arrayBuffer(),
        );

        if (!active) return;
        setDocumentUrl(documentData);
      })
      .catch((err) => {
        if (!active) return;

        setError(
          err.error?.message
            || 'Unable to open the document for review.',
        );
      });

    return () => {
      active = false;
    };
  }, [
    recipientId,
    task?.document?.id,
    task?.external_signing_required,
    documentRefreshKey,
  ]);

  useEffect(() => {
    if (
      !documentUrl
      || task?.external_signing_required
      || task?.status !== 'notified'
    ) return;

    let active = true;
    signatureApi.viewed(recipientId)
      .then(() => {
        if (!active) return;
        setTask((current) => (current ? {
          ...current,
          viewed_at: current.viewed_at || new Date().toISOString(),
          status: current.status === 'notified' ? 'viewed' : current.status,
        } : current));
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, [documentUrl, recipientId, task?.external_signing_required, task?.status]);

  const sign = async () => {
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      await signatureApi.submit(recipientId, {
        consent,
        signature_style: signatureStyle,
      });
      setSuccess('Your signature was submitted with the authoritative server timestamp.');
      setConsent(false);
      await load();
      setDocumentRefreshKey((value) => value + 1);
    } catch (err) {
      setError(err.error?.message || 'Unable to sign this document.');
    } finally {
      setBusy(false);
    }
  };

  const decline = async () => {
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      await signatureApi.decline(recipientId, declineReason.trim());
      setDeclineReason('');
      setShowDecline(false);
      setSuccess('Decline recorded and a discussion was opened.');
      await load();
    } catch (err) {
      setError(err.error?.message || 'Unable to decline this document.');
    } finally {
      setBusy(false);
    }
  };



  if (!task) {
    return (
      <div className="grid min-h-screen place-items-center bg-slate-100 text-sm text-slate-500">
        Loading signing workspace…
      </div>
    );
  }

  const reviewComplete = Boolean(task.viewed_at) || task.status === 'signed';
  const signed = task.status === 'signed';
  const requestComplete = task.request_status === 'completed';
  const generatedSignature = task.signature_name || task.signature_preview;
  const signingDate = task.signed_at
    ? formatDay(task.signed_at)
    : 'Set by Kinetic at submission';

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="flex min-h-16 items-center justify-between gap-4 px-5 lg:px-8">
          <div className="flex min-w-0 items-center gap-4">
            <Link
              to="/tasks"
              className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
              aria-label="Back to tasks"
            >
              <ArrowLeft size={17} />
            </Link>
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-700">Kinetic secure signing</p>
              <h1 className="truncate text-base font-bold text-slate-950">{task.document.title}</h1>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge tone={statusTone(task.status)}>{task.status.replaceAll('_', ' ')}</Badge>
            <span className="hidden text-xs text-slate-500 md:inline">Due {formatDate(task.due_at)}</span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1680px] p-4 lg:p-6">
        {error && <div className="mb-4"><Alert type="error">{error}</Alert></div>}
        {success && <div className="mb-4"><Alert type="success">{success}</Alert></div>}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
          <section className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
              <div>
                <p className="font-semibold text-slate-950">Document review</p>
                <p className="mt-1 text-xs text-slate-500">Required fields assigned to you are highlighted on the PDF.</p>
              </div>
              <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
                <ShieldCheck size={15} className="text-blue-700" />
                PDF signing workspace
              </div>
            </div>
            <div className="max-h-[calc(100vh-150px)] overflow-auto">
              {documentUrl ? (
                <PdfSigningViewer url={documentUrl} fields={currentFields} />
              ) : (
                <div className="grid min-h-[70vh] place-items-center text-sm text-slate-500">Preparing document…</div>
              )}
            </div>
          </section>

          <aside className="space-y-4 xl:max-h-[calc(100vh-110px)] xl:overflow-auto xl:pr-1">
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Signing progress</p>
              <div className="mt-4 space-y-5">
                <Step
                  number="1"
                  title="Review document"
                  description={reviewComplete ? 'Document review recorded.' : 'Read the full document before signing.'}
                  complete={reviewComplete}
                  active={!reviewComplete}
                />
                <Step
                  number="2"
                  title="Confirm signature"
                  description={signed ? 'Your electronic signature is complete.' : 'Kinetic generates it from your official employee name.'}
                  complete={signed}
                  active={reviewComplete && !signed}
                />
                <Step
                  number="3"
                  title="Complete request"
                  description={requestComplete ? 'All required signatories have completed the document.' : `${task.signed_count} of ${task.recipient_count} signatories complete.`}
                  complete={requestComplete}
                  active={signed && !requestComplete}
                />
              </div>
            </section>

            {!task.external_signing_required && !closed && (
              <section className="rounded-2xl border border-blue-200 bg-white p-5 shadow-sm">
                <div className="flex items-start gap-3">
                  <UserRoundCheck className="mt-0.5 shrink-0 text-blue-700" size={20} />
                  <div>
                    <h2 className="font-bold text-slate-950">Your electronic signature</h2>
                    <p className="mt-1 text-xs leading-5 text-slate-500">Generated from the official name on your Kinetic employee profile. The signed identity cannot be typed over.</p>
                  </div>
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Signature</p>
                  <p
                    className={`mt-2 text-4xl leading-tight text-slate-950 ${
                      signatureStyle === 'calligraphy_2'
                        ? ''
                        : 'font-serif italic'
                    }`}
                    style={
                      signatureStyle === 'calligraphy_2'
                        ? HANDWRITTEN_SIGNATURE_STYLE
                        : undefined
                    }
                  >
                    {generatedSignature}
                  </p>
                  <p className="mt-3 text-xs text-slate-500">Official signer: {task.name}</p>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setSignatureStyle('calligraphy_1')}
                    className={`rounded-xl border p-3 text-left ${signatureStyle === 'calligraphy_1' ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white'}`}
                  >
                    <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
                      Classic
                    </span>
                    <span className="mt-1 block font-serif text-xl italic">
                      {generatedSignature}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSignatureStyle('calligraphy_2')}
                    className={`rounded-xl border p-3 text-left ${signatureStyle === 'calligraphy_2' ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white'}`}
                  >
                    <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
                      Handwritten
                    </span>
                    <span
                      className="mt-1 block text-2xl leading-tight"
                      style={HANDWRITTEN_SIGNATURE_STYLE}
                    >
                      {generatedSignature}
                    </span>
                  </button>
                </div>

                <div className="mt-4 flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <CalendarDays size={18} className="text-slate-500" />
                  <div>
                    <p className="text-xs font-semibold text-slate-800">Date signed</p>
                    <p className="text-xs text-slate-500">{signingDate}{task.signed_at ? '' : ' · authoritative server timestamp'}</p>
                  </div>
                </div>

                <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-blue-100 bg-blue-50 p-3">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(event) => setConsent(event.target.checked)}
                    className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-700"
                  />
                  <span className="text-xs leading-5 text-blue-950">I have reviewed this document and intend <strong>{generatedSignature}</strong> to be my electronic signature.</span>
                </label>

                <Button
                  className="mt-4 w-full"
                  size="lg"
                  disabled={busy || !consent || !reviewComplete}
                  onClick={sign}
                >
                  <Send size={16} /> Sign &amp; submit
                </Button>
                {!reviewComplete && (
                  <p className="mt-2 text-center text-[11px] text-slate-500">The document must finish loading before submission is enabled.</p>
                )}

                <button
                  type="button"
                  onClick={() => setShowDecline((value) => !value)}
                  className="mt-3 w-full text-center text-xs font-semibold text-red-600 hover:text-red-700"
                >
                  I cannot sign this document
                </button>

                {showDecline && (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <label className="text-xs font-semibold text-slate-700" htmlFor="decline-reason">Reason for declining</label>
                    <textarea
                      id="decline-reason"
                      rows={3}
                      value={declineReason}
                      onChange={(event) => setDeclineReason(event.target.value)}
                      className="mt-2 w-full rounded-lg border border-slate-300 p-3 text-sm outline-none focus:border-red-400"
                    />
                    <Button
                      className="mt-2 w-full"
                      variant="danger"
                      size="sm"
                      disabled={busy || declineReason.trim().length < 2}
                      onClick={decline}
                    >
                      <XCircle size={14} /> Decline and open discussion
                    </Button>
                  </div>
                )}
              </section>
            )}

            {signed && (
              <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
                <div className="flex gap-3">
                  <CheckCircle2 className="mt-0.5 shrink-0 text-emerald-700" size={21} />
                  <div>
                    <h2 className="font-bold text-emerald-950">Your signature is complete</h2>
                    <p
                      className={`mt-1 text-3xl text-slate-950 ${
                        task.signature_style === 'calligraphy_2'
                          ? ''
                          : 'font-serif italic'
                      }`}
                      style={
                        task.signature_style === 'calligraphy_2'
                          ? HANDWRITTEN_SIGNATURE_STYLE
                          : undefined
                      }
                    >
                      {task.signature_name}
                    </p>
                    <p className="mt-2 text-xs leading-5 text-emerald-900">Signed {formatDate(task.signed_at)}. Kinetic retained the consent event and server timestamp.</p>
                  </div>
                </div>
                {requestComplete && task.signed_document ? (
                  <a
                    href={signatureApi.signedDocumentUrl(recipientId)}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800"
                  >
                    <FileCheck2 size={16} /> View final signed document
                  </a>
                ) : (
                  <div className="mt-4 flex items-center gap-2 rounded-lg bg-white/70 p-3 text-xs text-emerald-900">
                    <Clock3 size={15} />
                    Waiting for {task.recipient_count - task.signed_count === 1 ? '1 remaining signatory' : `${task.recipient_count - task.signed_count} remaining signatories`}.
                  </div>
                )}
              </section>
            )}

            {task.external_signing_required && (
              <section className="rounded-2xl border border-blue-200 bg-blue-50 p-5 text-blue-950">
                <div className="flex gap-3">
                  <ExternalLink className="mt-0.5 shrink-0" size={19} />
                  <div>
                    <h2 className="font-bold">Provider-hosted QES</h2>
                    <p className="mt-1 text-xs leading-5">This request uses the identity-verified provider ceremony. Review the source document here, then complete signing from the invitation sent by the provider.</p>
                  </div>
                </div>
              </section>
            )}

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-500">Signing parties</p>
                  <p className="mt-1 text-xs text-slate-500">{task.signing_mode === 'parallel' ? 'Parallel signing' : 'Sequential signing'}</p>
                </div>
                <Badge tone={requestComplete ? 'green' : 'blue'}>{task.signed_count}/{task.recipient_count}</Badge>
              </div>
              <div className="mt-4 space-y-3">
                {(task.signers || []).map((signer) => (
                  <div key={signer.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 p-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900">{signer.name}</p>
                      <p className="truncate text-xs text-slate-500">{signer.role_label || 'Signatory'}{signer.signed_at ? ` · ${formatDay(signer.signed_at)}` : ''}</p>
                    </div>
                    <Badge tone={statusTone(signer.status)}>{signer.status}</Badge>
                  </div>
                ))}
              </div>
            </section>

            <SignatureDiscussionPanel
              recipientId={recipientId}
              allowResolve
            />
          </aside>
        </div>
      </main>
    </div>
  );
}
