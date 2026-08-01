import { useId } from 'react';

export default function Select({ label, error, hint, className = '', children, id, required, ...props }) {
  const generatedId = useId();
  const selectId = id || generatedId;
  const messageId = `${selectId}-message`;

  return (
    <label htmlFor={selectId} className="block space-y-1.5">
      {label && (
        <span className="flex items-center gap-1 text-[13px] font-semibold text-slate-700">
          {label}
          {required && <span className="text-red-600" aria-hidden="true">*</span>}
        </span>
      )}
      <select
        id={selectId}
        required={required}
        aria-invalid={Boolean(error)}
        aria-describedby={(error || hint) ? messageId : undefined}
        className={`min-h-10 w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition disabled:cursor-not-allowed disabled:bg-slate-100 ${
          error
            ? 'border-red-400 focus:border-red-500 focus:ring-4 focus:ring-red-100'
            : 'border-slate-300 hover:border-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100'
        } ${className}`}
        {...props}
      >
        {children}
      </select>
      {(error || hint) && (
        <span id={messageId} className={`block text-xs leading-5 ${error ? 'text-red-600' : 'text-slate-500'}`}>
          {error || hint}
        </span>
      )}
    </label>
  );
}
