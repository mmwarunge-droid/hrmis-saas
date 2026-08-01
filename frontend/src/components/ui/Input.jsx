import { useId } from 'react';

export default function Input({
  label,
  error,
  hint,
  className = '',
  id,
  required,
  icon: Icon,
  ...props
}) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const messageId = `${inputId}-message`;

  return (
    <label htmlFor={inputId} className="block space-y-1.5">
      {label && (
        <span
          className={`flex items-center gap-1 text-[13px] font-semibold text-slate-700 ${
            required
              ? "after:ml-1 after:text-red-600 after:content-['*']"
              : ""
          }`}
        >
          {label}
        </span>
      )}
      <span className="relative block">
        {Icon && (
          <Icon
            aria-hidden="true"
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
        )}
        <input
          id={inputId}
          required={required}
          aria-invalid={Boolean(error)}
          aria-describedby={(error || hint) ? messageId : undefined}
          className={`min-h-10 w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500 ${Icon ? 'pl-9' : ''} ${
            error
              ? 'border-red-400 focus:border-red-500 focus:ring-4 focus:ring-red-100'
              : 'border-slate-300 hover:border-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100'
          } ${className}`}
          {...props}
        />
      </span>
      {(error || hint) && (
        <span id={messageId} className={`block text-xs leading-5 ${error ? 'text-red-600' : 'text-slate-500'}`}>
          {error || hint}
        </span>
      )}
    </label>
  );
}
