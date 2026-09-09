import { useContext, useEffect, useId, useRef, useState, useMemo } from 'react';
import { captureWorkflow, errorState, registerWorkflow } from '../../utils/formFeedback.js';
import WorkflowFeedback from './WorkflowFeedback.jsx';
import { WorkflowContext, FormFeedbackContext } from './WorkflowContext.js';
import useFormDraft, { draftSnapshot } from './useFormDraft.js';
import { UNSAFE_DataRouterContext } from 'react-router-dom';

export default function Form({ children, onSubmit, error, draft, values, successMessage = 'Changes saved successfully.', ...props }) {
  const dataRouter = useContext(UNSAFE_DataRouterContext);
  const id = useId();
  const root = useRef(null);
  const exitRef = useRef(null);
  const working = useRef(false);
  const dirty = useRef(false);
  const localFilePending = useRef(false);
  const failed = useRef(false);
  const mutationSucceeded = useRef(false);
  const exitCancelled = useRef(null);
  const requests = useRef(0);
  const pending = useRef(0);
  const drained = useRef([]);
  const waitForRequests = () => pending.current === 0 ? Promise.resolve() : new Promise((resolve) => drained.current.push(resolve));
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [exit, setExit] = useState(null);
  const persistence = useFormDraft(draft, { paused: busy || Boolean(exit) });
  useEffect(() => {
    if (exit) { exitRef.current?.focus(); exitRef.current?.scrollIntoView?.({ block: 'center', behavior: 'smooth' }); }
  }, [exit]);
  const modal = useContext(WorkflowContext);
  const guard = useRef(null);
  const snapshot = draftSnapshot(draft?.data ?? values);
  const previousSnapshot = useRef(snapshot);
  useEffect(() => {
    if (snapshot !== previousSnapshot.current && !working.current) dirty.current = true;
    previousSnapshot.current = snapshot;
  }, [snapshot]);
  guard.current = {
    dirty: () => dirty.current && !(persistence.enabled && persistence.isSaved && !localFilePending.current),
    busy: () => working.current || pending.current > 0,
    close: (action, cancel) => {
      exitCancelled.current = cancel;
      if (working.current || pending.current > 0) return;
      if (guard.current.dirty()) setExit(() => action); else action();
    },
  };
  useEffect(() => modal?.register(id, guard), [modal, id]);
  useEffect(() => registerWorkflow(id, {
    dirty: () => guard.current.dirty() && !(working.current && mutationSucceeded.current && !failed.current),
    submitting: () => working.current,
    leave: (action, cancel) => guard.current.close(action, cancel),
    start: (method) => { pending.current += 1; if (['post', 'put', 'patch', 'delete'].includes(method)) requests.current += 1; },
    error: (err) => { failed.current = true; setFeedback(errorState(err)); },
    settle: (err) => { if (err) { failed.current = true; setFeedback(errorState(err)); } else if (requests.current > 0) mutationSucceeded.current = true;
      pending.current = Math.max(0, pending.current - 1);
      if (pending.current === 0) drained.current.splice(0).forEach((resolve) => resolve());
    },
  }), [id]);
  useEffect(() => {
    const unload = (event) => { if (guard.current.dirty()) { event.preventDefault(); event.returnValue = ''; } };
    const navigate = (event) => {
      if (dataRouter) return;
      const anchor = event.target.closest?.('a[href]');
      if (!guard.current.dirty() || !anchor || anchor.target === '_blank' || anchor.hasAttribute('download') || event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return;
      if (anchor.href === window.location.href || anchor.getAttribute('href').startsWith('#')) return;
      event.preventDefault(); event.stopPropagation();
      guard.current.close(() => window.location.assign(anchor.href));
    };
    window.addEventListener('beforeunload', unload);
    document.addEventListener('click', navigate, true);
    return () => { window.removeEventListener('beforeunload', unload); document.removeEventListener('click', navigate, true); };
  }, [dataRouter]);
  const submit = async (event) => {
    event.preventDefault();
    if (working.current || exit) return;
    if (pending.current > 0) { setFeedback({ kind: 'info', message: 'Another action is still processing. Please wait before submitting.' }); return; }
    if (persistence.candidate) { setFeedback(errorState('Resume or discard the saved draft before submitting a new workflow.')); return; }
    const invalid = event.nativeEvent?.submitter?.formNoValidate ? [] : [...root.current.elements].filter((control) => control.willValidate && !control.validity.valid && !(control.type === 'file' && control.files?.length));
    if (invalid.length) {
      setFeedback({ kind: 'error', message: 'Please correct the following fields and try again.', issues: invalid.map((control) => ({ field: control.name || control.getAttribute('aria-label') || control.labels?.[0]?.textContent || '', message: control.validationMessage })) });
      return;
    }
    working.current = true; failed.current = false; mutationSucceeded.current = false; requests.current = 0;
    setBusy(true); setFeedback(null); captureWorkflow(id);
    try {
      const result = await onSubmit?.(event);
      await waitForRequests();
      if (result?.success === false && !failed.current) {
        failed.current = true;
        setFeedback(errorState(result.error || 'This action was not completed. Review the form and try again.'));
      }
      if (!failed.current && (requests.current > 0 || result?.success)) {
        dirty.current = false; localFilePending.current = false;
        if (persistence.enabled) await persistence.complete();
        setFeedback({ kind: 'success', message: successMessage });
      }
    } catch (err) { failed.current = true; setFeedback(errorState(err)); }
    finally { await waitForRequests(); working.current = false; setBusy(false); }
  };
  const externalFeedback = useMemo(() => error ? errorState(error) : null, [error]);
  const draftFeedback = useMemo(() => persistence.failure ? errorState(persistence.failure) : null, [persistence.failure]);
  const visibleFeedback = draftFeedback || externalFeedback || feedback;
  return <FormFeedbackContext.Provider value={visibleFeedback}><form {...props} data-workflow-owner={id} ref={root} noValidate aria-busy={busy} onSubmit={submit}
    onClickCapture={() => captureWorkflow(id)}
    onChangeCapture={(event) => { dirty.current = true; if (event.target.type === 'file') localFilePending.current = Boolean(event.target.files?.length); }}>
    <WorkflowFeedback state={visibleFeedback} rootRef={root} />
    {persistence.enabled && <div className="col-span-full space-y-2 rounded-lg border bg-slate-50 p-3 text-sm">
      {persistence.candidate ? <><p>A saved draft is available. Resuming replaces the current entries with the saved version. Resume or discard it before saving a new draft.</p><button type="button" className="underline mr-4" onClick={() => { persistence.resume(); dirty.current = true; }}>Resume draft</button><button type="button" className="underline" onClick={persistence.discard}>Discard saved draft</button></> : <button type="button" className="font-semibold underline" disabled={busy || persistence.busy} onClick={persistence.save}>{persistence.busy ? 'Saving draft…' : 'Save draft'}</button>}
      {persistence.status && <p role="status">{persistence.status}</p>}
      <p className="text-xs text-slate-500">{persistence.autoSave ? 'Changes save automatically after you pause typing. ' : ''}Drafts are private to your account and organization. Reattach local files when resuming.</p>
      {persistence.failure && <button type="button" className="underline" onClick={persistence.reload}>Reload saved drafts</button>}

    </div>}
    {exit && <div ref={exitRef} tabIndex={-1} role="alertdialog" aria-label="Unsaved changes" className="col-span-full rounded-lg border border-amber-300 bg-amber-50 p-4 space-y-3">
      <p>You have unsaved changes. Choose how to leave this form.</p>
      {persistence.enabled && <button type="button" className="underline mr-4" disabled={persistence.busy} onClick={async () => { if (await persistence.save()) { dirty.current = false; exit(); } }}>Save draft and exit</button>}
      <button type="button" className="underline mr-4" onClick={async () => { if (!persistence.enabled || await persistence.discard()) { dirty.current = false; exit(); } }}>Discard changes</button>
      <button type="button" className="underline" onClick={() => { setExit(null); exitCancelled.current?.(); }}>Continue editing</button>
    </div>}
    <fieldset disabled={busy || Boolean(exit)} className={`min-w-0 col-span-full border-0 p-0 ${props.className || ''}`}>{children}</fieldset>
    {busy && <p role="status" className="col-span-full text-sm">Submitting… Please wait.</p>}
  </form></FormFeedbackContext.Provider>;
}
