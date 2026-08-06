import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from 'react';
import { CheckCircle2, CircleAlert, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

const tones = {
  success: {
    icon: CheckCircle2,
    className: 'border-emerald-200 bg-emerald-50 text-emerald-950',
  },
  error: {
    icon: CircleAlert,
    className: 'border-red-200 bg-red-50 text-red-950',
  },
  info: {
    icon: Info,
    className: 'border-blue-200 bg-blue-50 text-blue-950',
  },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const sequence = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((items) => items.filter((item) => item.id !== id));
  }, []);

  const push = useCallback((message, options = {}) => {
    sequence.current += 1;
    const id = sequence.current;
    const toast = {
      id,
      message,
      title: options.title || '',
      tone: options.tone || 'success',
    };
    setToasts((items) => [...items.slice(-3), toast]);
    window.setTimeout(() => dismiss(id), options.duration || 4500);
    return id;
  }, [dismiss]);

  const value = useMemo(() => ({
    push,
    success: (message, options = {}) => push(message, {
      ...options,
      tone: 'success',
    }),
    error: (message, options = {}) => push(message, {
      ...options,
      tone: 'error',
    }),
    info: (message, options = {}) => push(message, {
      ...options,
      tone: 'info',
    }),
    dismiss,
  }), [dismiss, push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed right-4 top-20 z-[100] flex w-[min(92vw,390px)] flex-col gap-2"
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map((toast) => {
          const tone = tones[toast.tone] || tones.info;
          const Icon = tone.icon;
          return (
            <div
              key={toast.id}
              role={toast.tone === 'error' ? 'alert' : 'status'}
              className={`pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 shadow-lg ${tone.className}`}
            >
              <Icon className="mt-0.5 shrink-0" size={18} />
              <div className="min-w-0 flex-1">
                {toast.title && (
                  <p className="text-sm font-bold">{toast.title}</p>
                )}
                <p className="text-sm leading-5">{toast.message}</p>
              </div>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                className="grid h-7 w-7 shrink-0 place-items-center rounded-lg hover:bg-black/5"
                aria-label="Dismiss notification"
              >
                <X size={15} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}
