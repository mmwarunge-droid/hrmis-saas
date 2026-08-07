import { useRef } from 'react';

export default function Tabs({
  items,
  value,
  onChange,
  className = '',
  ariaLabel = 'Sections',
  idPrefix = 'kinetic-tabs',
}) {
  const buttonRefs = useRef(new Map());

  const focusItem = (index) => {
    const safeIndex = (index + items.length) % items.length;
    const item = items[safeIndex];
    onChange(item.value);
    buttonRefs.current.get(item.value)?.focus();
  };

  const handleKeyDown = (event, index) => {
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      focusItem(index + 1);
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      focusItem(index - 1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      focusItem(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      focusItem(items.length - 1);
    }
  };

  return (
    <div className={`overflow-x-auto border-b border-slate-200 ${className}`}>
      <div role="tablist" aria-label={ariaLabel} className="flex min-w-max gap-1">
        {items.map((item, index) => {
          const selected = value === item.value;
          return (
            <button
              key={item.value}
              ref={(node) => {
                if (node) buttonRefs.current.set(item.value, node);
                else buttonRefs.current.delete(item.value);
              }}
              id={`${idPrefix}-tab-${item.value}`}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={`${idPrefix}-panel-${item.value}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(item.value)}
              onKeyDown={(event) => handleKeyDown(event, index)}
              className={`relative px-3 py-3 text-sm font-semibold transition after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full ${
                selected
                  ? 'text-blue-700 after:bg-blue-700'
                  : 'text-slate-500 after:bg-transparent hover:text-slate-900'
              }`}
            >
              {item.label}
              {item.count !== undefined && (
                <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">{item.count}</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
