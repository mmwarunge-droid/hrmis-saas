import { useEffect, useRef, useId } from 'react';
import { fieldLabel } from '../../utils/formFeedback.js';

function locate(root, field) {
  const controls = [...(root?.querySelectorAll('input,select,textarea') || [])];
  const normalize = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  return controls.find((control) => control.name === field || (field === 'due_at' && control.name === 'due_date'))
    || controls.find((control) => normalize(control.name) === normalize(field))
    || controls.find((control) => normalize(control.getAttribute('aria-label')) === normalize(fieldLabel(field)))
    || controls.find((control) => normalize(control.labels?.[0]?.textContent) === normalize(fieldLabel(field)));
}
export default function WorkflowFeedback({ state, rootRef }) {
  const ref = useRef(null);
  const summaryId = useId();
  useEffect(() => {
    const root = rootRef?.current;
    root?.querySelectorAll('[data-form-invalid]').forEach((control) => {
      control.removeAttribute('data-form-invalid');
      control.removeAttribute('aria-errormessage');
      control.setAttribute('aria-invalid', 'false');
    });
    if (state?.kind !== 'error') return;
    for (const issue of state.issues || []) {
      const control = locate(root, issue.field);
      if (control) {
        control.setAttribute('data-form-invalid', 'true');
        control.setAttribute('aria-invalid', 'true');
        control.setAttribute('aria-errormessage', summaryId);
      }
    }
    ref.current?.focus();
    ref.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' });
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
