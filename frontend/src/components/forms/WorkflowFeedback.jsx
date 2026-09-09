import { useEffect, useRef, useId } from 'react';
import { fieldLabel } from '../../utils/formFeedback.js';

function locate(root, field) {
  const controls = [...(root?.querySelectorAll('input,select,textarea') || [])];
  const normalize = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  return controls.find((control) => control.name === field || (field === 'due_at' && control.name === 'due_date'))
    || controls.find((control) => normalize(control.name) === normalize(field))
    || controls.find((control) => normalize(control.getAttribute('aria-label')) === normalize(fieldLabel(field)))
    || controls.find((control) => normalize(control.labels?.[0]?.querySelector('span')?.textContent || control.labels?.[0]?.textContent) === normalize(fieldLabel(field)));
}
export default function WorkflowFeedback({ state, rootRef }) {
  const ref = useRef(null);
  const summaryId = useId();
  useEffect(() => {
    const root = rootRef?.current;
    if (state?.kind !== 'error') return;
    const marked = [];
    const messages = [];
    const byControl = new Map();
    for (const [index, issue] of (state.issues || []).entries()) {
      const control = locate(root, issue.field);
      if (!control) continue;
      if (byControl.has(control)) { byControl.get(control).textContent += ` ${issue.message}`; continue; }
      const message = document.createElement('span');
      message.id = `${summaryId}-field-${index}`;
      message.className = 'block text-xs text-red-700 mt-1';
      message.textContent = issue.message;
      message.setAttribute('data-workflow-field-error', summaryId);
      (control.closest('label') || control).insertAdjacentElement('afterend', message);
      byControl.set(control, message);
      messages.push(message);
      marked.push({ control, invalid: control.getAttribute('aria-invalid'), description: control.getAttribute('aria-describedby') });
      control.setAttribute('data-form-invalid', 'true');
      control.setAttribute('data-form-error-owner', summaryId);
      control.setAttribute('aria-invalid', 'true');
      control.setAttribute('aria-errormessage', message.id);
      control.setAttribute('aria-describedby', [control.getAttribute('aria-describedby'), message.id].filter(Boolean).join(' '));
    }
    const dialogs = document.querySelectorAll('[data-modal-overlay]');
    const foreground = dialogs[dialogs.length - 1];
    if (!foreground || foreground.contains(ref.current)) {
    ref.current?.focus();
      ref.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' });
    }
    return () => {
      messages.forEach((message) => message.remove());
      marked.reverse().forEach(({ control, invalid, description }) => {
        if (control.getAttribute('data-form-error-owner') !== summaryId) return;
        control.removeAttribute('data-form-error-owner');
        control.removeAttribute('data-form-invalid');
        control.removeAttribute('aria-errormessage');
        if (invalid === null) control.removeAttribute('aria-invalid'); else control.setAttribute('aria-invalid', invalid);
        if (description === null) control.removeAttribute('aria-describedby'); else control.setAttribute('aria-describedby', description);
      });
    };
  }, [state, rootRef, summaryId]);
  if (!state) return null;
  return <div id={summaryId} ref={ref} tabIndex={-1} role={state.kind === 'error' ? 'alert' : 'status'}
    className={`col-span-full rounded-lg border p-4 text-sm outline-none ${state.kind === 'error' ? 'border-red-300 bg-red-50 text-red-900' : state.kind === 'success' ? 'border-green-200 bg-green-50 text-green-900' : 'border-blue-200 bg-blue-50 text-blue-900'}`}>
    <p className="font-semibold">{state.message}</p>
    {Boolean(state.issues?.length) && <ul className="mt-2 list-disc space-y-1 pl-5">{state.issues.map((issue, index) => <li key={`${issue.field}-${index}`}>
      <button type="button" className="text-left underline underline-offset-2" onClick={() => {
        const control = locate(rootRef?.current, issue.field);
        control?.focus(); control?.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
      }}>{issue.field ? `${fieldLabel(issue.field)}: ` : ''}{issue.message}</button>
    </li>)}</ul>}
    {state.status === 401 && !state.authenticationAttempt && <a className="mt-2 inline-block underline" href="/login" target="_blank" rel="noreferrer">Sign in in a new tab, then return and retry</a>}
  </div>;
}
