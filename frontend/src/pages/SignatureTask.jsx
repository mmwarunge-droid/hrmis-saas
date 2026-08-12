import { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ExternalLink, MessageSquare, Send, XCircle } from 'lucide-react';
import { useParams } from 'react-router-dom';

import { documentApi } from '../api/documentApi.js';
import { signatureApi } from '../api/signatureApi.js';
import Alert from '../components/ui/Alert.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Input from '../components/ui/Input.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';

function formatDate(value) {
  if (!value) return 'Not set';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function SignatureTask() {
  const { recipientId } = useParams();
  const [task, setTask] = useState(null);
  const [discussion, setDiscussion] = useState(null);
  const [documentUrl, setDocumentUrl] = useState('');
  const [signatureName, setSignatureName] = useState('');
  const [comment, setComment] = useState('');
  const [declineReason, setDeclineReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const closed = useMemo(
    () => ['signed', 'declined', 'expired', 'skipped'].includes(task?.status),
    [task?.status],
  );

  const load = useCallback(async () => {
    const [taskResponse, discussionResponse] = await Promise.all([
      signatureApi.recipient(recipientId),
      signatureApi.discussion(recipientId),
    ]);
    setTask(taskResponse.data);
    setDiscussion(discussionResponse.data);
    setSignatureName((current) => current || taskResponse.data.name || '');
  }, [recipientId]);

  useEffect(() => {
    load().catch((err) => setError(err.error?.message || 'Unable to load signature task.'));
  }, [load]);

  useEffect(() => {
    let active = true;
    let objectUrl = '';
    if (!task?.document?.id) return undefined;
    documentApi.content(task.document.id)
      .then((response) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(response.data);
        setDocumentUrl(objectUrl);
        if (!task.external_signing_required && ['notified', 'viewed'].includes(task.status)) {
          signatureApi.viewed(task.id).catch(() => {});
        }
      })
      .catch((err) => setError(err.error?.message || 'Unable to open the document for review.'));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [task?.document?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const sign = async () => {
    setBusy(true); setError(''); setSuccess('');
    try {
      await signatureApi.sign(recipientId, signatureName.trim());
      setSuccess('Signature recorded with the current date and time.');
      await load();
    } catch (err) {
      setError(err.error?.message || 'Unable to sign this document.');
    } finally { setBusy(false); }
  };

  const decline = async () => {
    setBusy(true); setError(''); setSuccess('');
    try {
      await signatureApi.decline(recipientId, declineReason.trim());
      setDeclineReason('');
      setSuccess('Decline recorded and a discussion was opened.');
      await load();
    } catch (err) {
      setError(err.error?.message || 'Unable to decline this document.');
    } finally { setBusy(false); }
  };

  const addComment = async () => {
    setBusy(true); setError('');
    try {
      await signatureApi.comment(recipientId, comment.trim());
      setComment('');
      await load();
    } catch (err) {
      setError(err.error?.message || 'Unable to add comment.');
    } finally { setBusy(false); }
  };

  const resolve = async () => {
    setBusy(true); setError('');
    try {
      await signatureApi.resolveDiscussion(recipientId);
      await load();
    } catch (err) {
      setError(err.error?.message || 'Unable to resolve discussion.');
    } finally { setBusy(false); }
  };

  if (!task) return <p className="p-6 text-sm text-slate-500">Loading signature task…</p>;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Document action"
        title={task.subject}
        description={`${task.document.title} · due ${formatDate(task.due_at)}`}
      />
      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-semibold text-slate-950">Secure document review</p>
            <p className="mt-1 text-sm text-slate-500">The document is streamed for in-browser review. Kinetic does not present a download action in this workflow.</p>
          </div>
          <Badge tone={task.status === 'signed' ? 'green' : task.status === 'declined' ? 'red' : 'amber'}>
            {task.status.replaceAll('_', ' ')}
          </Badge>
        </div>
        <div className="mt-4 min-h-[68vh] overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
          {documentUrl ? (
            <iframe title={`Review ${task.document.title}`} src={documentUrl} className="h-[68vh] w-full" />
          ) : (
            <div className="grid h-[68vh] place-items-center text-sm text-slate-500">Preparing document viewer…</div>
          )}
        </div>
      </Card>

      {!task.external_signing_required && !closed && (
        <Card>
          <h2 className="font-bold text-slate-950">Sign or decline</h2>
          <p className="mt-1 text-sm text-slate-600">Type your legal name as your electronic signature. Kinetic records the signature name and server timestamp in the audit history.</p>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-blue-100 bg-blue-50/60 p-4">
              <Input label="Typed signature" value={signatureName} onChange={(event) => setSignatureName(event.target.value)} />
              <p className="mt-3 font-serif text-3xl italic text-slate-900">{signatureName || 'Your signature'}</p>
              <Button className="mt-4" disabled={busy || signatureName.trim().length < 2} onClick={sign}>
                <Send size={15} /> Submit signature
              </Button>
            </div>
            <div className="rounded-lg border border-rose-100 bg-rose-50/50 p-4">
              <label className="block text-sm font-semibold text-slate-700" htmlFor="decline-reason">Reason for declining</label>
              <textarea id="decline-reason" className="mt-2 min-h-28 w-full rounded-lg border border-slate-300 bg-white p-3 text-sm" value={declineReason} onChange={(event) => setDeclineReason(event.target.value)} />
              <Button className="mt-4" variant="danger" disabled={busy || declineReason.trim().length < 2} onClick={decline}>
                <XCircle size={15} /> Decline and open discussion
              </Button>
            </div>
          </div>
        </Card>
      )}

      {task.status === 'signed' && (
        <Card>
          <h2 className="font-bold text-slate-950">Signing record</h2>
          <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">Electronic signature</p>
            <p className="mt-2 font-serif text-3xl italic text-slate-950">{task.signature_name}</p>
            <p className="mt-2 text-sm text-slate-600">Signed {formatDate(task.signed_at)}. The server timestamp and typed signature are retained in Kinetic's signature audit record.</p>
          </div>
        </Card>
      )}

      {task.external_signing_required && (
        <Alert type="info"><ExternalLink size={15} className="inline" /> This request uses the provider-hosted QES ceremony. Review the source here, then complete signing from the provider invitation.</Alert>
      )}

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="flex items-center gap-2 font-bold text-slate-950"><MessageSquare size={17} /> Document discussion</p>
            <p className="mt-1 text-sm text-slate-500">Reply to HR or mention an active Kinetic user using their work email, for example @legal@example.com.</p>
          </div>
          {discussion?.status === 'open' ? (
            <Button size="sm" variant="secondary" disabled={busy} onClick={resolve}><CheckCircle2 size={15} /> Mark resolved</Button>
          ) : <Badge tone="green">Resolved</Badge>}
        </div>
        <div className="mt-4 space-y-3">
          {(discussion?.comments || []).map((item) => (
            <div key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="flex justify-between gap-3 text-xs text-slate-500"><strong className="text-slate-800">{item.author_name}</strong><span>{formatDate(item.created_at)}</span></div>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{item.body}</p>
            </div>
          ))}
          {!(discussion?.comments || []).length && <p className="text-sm text-slate-500">No comments yet.</p>}
        </div>
        <div className="mt-4 flex gap-2">
          <textarea aria-label="Discussion comment" className="min-h-20 flex-1 rounded-lg border border-slate-300 p-3 text-sm" value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add context or @mention a colleague by work email" />
          <Button disabled={busy || comment.trim().length < 2} onClick={addComment}>Reply</Button>
        </div>
      </Card>
    </div>
  );
}
