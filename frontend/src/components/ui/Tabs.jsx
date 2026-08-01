export default function Tabs({ items, value, onChange, className = '', ariaLabel = 'Sections' }) {
  return (
    <div className={`overflow-x-auto border-b border-slate-200 ${className}`}>
      <div role="tablist" aria-label={ariaLabel} className="flex min-w-max gap-1">
        {items.map((item) => (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={value === item.value}
            onClick={() => onChange(item.value)}
            className={`relative px-3 py-3 text-sm font-semibold transition after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full ${
              value === item.value
                ? 'text-blue-700 after:bg-blue-700'
                : 'text-slate-500 after:bg-transparent hover:text-slate-900'
            }`}
          >
            {item.label}
            {item.count !== undefined && (
              <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">{item.count}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
