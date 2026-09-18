import { WorkflowContext } from '../forms/WorkflowContext.js';
import WorkflowFeedback from '../forms/WorkflowFeedback.jsx';
import { captureWorkflow, registerWorkflow, errorState } from '../../utils/formFeedback.js';
import { X } from 'lucide-react';
import { useEffect, useId, useRef, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';

import Button from './Button.jsx';

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

export default function Modal({
  open,
  title,
  description,
  children,
  footer = null,
  onClose,
  size = 'lg',
  error = null,
}) {
  const titleId = useId();
  const descriptionId = useId();
  const panelRef = useRef(null);
  const guards = useRef(new Map());
  const closeRef = useRef(onClose); useEffect(() => { closeRef.current = onClose; }, [onClose]);
  const [feedback, setFeedback] = useState(null);
  const pending = useRef(0);
  const externalFeedback = useMemo(() => error ? errorState(error) : null, [error]);
  const context = useMemo(() => ({ register: (id, guard) => {
    guards.current.set(id, guard); return () => guards.current.delete(id);
  } }), []);
  const requestClose = () => {
    if (pending.current || [...guards.current.values()].some((guard) => guard.current.busy())) return;
    const changed = [...guards.current.values()].filter((guard) => guard.current.dirty());
    const next = (index) => index < changed.length ? changed[index].current.close(() => next(index + 1)) : closeRef.current?.();
    next(0);
  };
  const requestCloseRef = useRef(requestClose); useEffect(() => { requestCloseRef.current = requestClose; });
  useEffect(() => {
    if (!open) return;
    return registerWorkflow(titleId, {
      start: () => { pending.current += 1; setFeedback(null); },
      settle: (err) => { pending.current = Math.max(0, pending.current - 1); if (err) setFeedback(errorState(err)); },
    });
  }, [open, titleId]);

  useEffect(() => {
    if (!open) return undefined;

    const previouslyFocused = document.activeElement;
    const previousOverflow = document.body.style.overflow;

    document.body.style.overflow = 'hidden';

    const handleKeyDown = (event) => {
      const dialogs = document.querySelectorAll('[data-modal-overlay]');
      if (dialogs[dialogs.length - 1] !== panelRef.current?.parentElement) return;
      if (event.key === 'Escape') {
        requestCloseRef.current();
        return;
      }

      if (event.key !== 'Tab' || !panelRef.current) return;

      const focusable = [
        ...panelRef.current.querySelectorAll(FOCUSABLE),
      ];

      if (focusable.length === 0) {
        event.preventDefault();
        panelRef.current.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (
        event.shiftKey
        && document.activeElement === first
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey
        && document.activeElement === last
      ) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    const focusTimer = window.setTimeout(() => {
      const firstFocusable =
        panelRef.current?.querySelector(FOCUSABLE);

      (firstFocusable || panelRef.current)?.focus();
    }, 0);

    return () => {
      window.clearTimeout(focusTimer);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener(
        'keydown',
        handleKeyDown,
      );
      previouslyFocused?.focus?.();
      setFeedback(null);
    };
  }, [open]);

  if (!open || typeof document === 'undefined') {
    return null;
  }

  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-xl',
    lg: 'max-w-3xl',
    xl: 'max-w-5xl',
  };

  return createPortal(
    <div
      onClickCapture={(event) => {
        const button = event.target.closest?.('button');
        if (button && /^cancel$/i.test(button.textContent.trim())) {
          event.preventDefault(); event.stopPropagation(); requestCloseRef.current(); return;
        }
        if (!event.target.closest?.('form')) captureWorkflow(titleId);
      }}
      data-workflow-owner={titleId}
      data-modal-overlay
      className="
        fixed inset-0 z-[100]
        flex items-center justify-center
        overflow-hidden
        bg-slate-950/50
        p-3
        backdrop-blur-[2px]
        sm:p-4
      "
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          requestCloseRef.current();
        }
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={
          description ? descriptionId : undefined
        }
        tabIndex={-1}
        className={`
          flex
          max-h-[calc(100dvh-1.5rem)]
          min-h-0 min-w-0
          w-full
          flex-col
          overflow-hidden
          rounded-xl
          border border-slate-200
          bg-white
          shadow-2xl
          outline-none
          motion-safe:animate-[kinetic-dialog-in_160ms_ease-out]
          sm:max-h-[calc(100dvh-2rem)]
          ${sizes[size] || sizes.lg}
        `}
      >
        <div
          className="
            flex shrink-0 items-start justify-between
            gap-4 border-b border-slate-200
            px-5 py-4 md:px-6
          "
        >
          <div className="min-w-0">
            <h2
              id={titleId}
              className="
                text-lg font-bold
                tracking-[-0.02em]
                text-slate-950
              "
            >
              {title}
            </h2>

            {description ? (
              <p
                id={descriptionId}
                className="
                  mt-1 text-sm leading-6
                  text-slate-500
                "
              >
                {description}
              </p>
            ) : null}
          </div>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label="Close dialog"
            onClick={requestClose}
            className="shrink-0"
          >
            <X size={18} />
          </Button>
        </div>

        <div
          data-modal-scroll-region
          className="
            min-h-0 flex-1
            overflow-y-auto
            overscroll-contain
            p-5 md:p-6
          "
        >
          <WorkflowContext.Provider value={context}>
            <WorkflowFeedback state={externalFeedback || feedback} rootRef={panelRef} />
            {children}
          </WorkflowContext.Provider>
        </div>

        {footer ? (
          <div
            data-modal-footer
            className="
              flex shrink-0 flex-wrap
              items-center justify-end
              gap-3
              border-t border-slate-200
              bg-white
              px-5 py-4
              shadow-[0_-8px_24px_rgba(15,23,42,0.05)]
              md:px-6
            "
          >
            {footer}
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
