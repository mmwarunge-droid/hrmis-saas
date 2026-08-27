import { ArrowRight, Search, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { navigationGroups, visibleNavigation } from '../../config/navigation.js';
import useAuth from '../../hooks/useAuth.js';
import usePermissions from '../../hooks/usePermissions.js';

export default function GlobalSearch({ open, onClose }) {
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef(null);
  const navigate = useNavigate();
  const { user } = useAuth();
  const { hasPermission, hasRole } = usePermissions();
  const hasEmployeeProfile = Boolean(user?.employee_profile);

  const closeSearch = useCallback(() => {
    setQuery('');
    setActiveIndex(0);
    onClose();
  }, [onClose]);

  const items = useMemo(
    () => visibleNavigation(navigationGroups, {
      hasPermission,
      hasRole,
      hasEmployeeProfile,
    })
      .flatMap((group) => group.links.map((item) => ({ ...item, group: group.label }))),
    [hasEmployeeProfile, hasPermission, hasRole],
  );

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return items.slice(0, 10);
    return items.filter((item) => (
      `${item.label} ${item.group} ${item.keywords || ''}`
        .toLowerCase()
        .includes(needle)
    ));
  }, [items, query]);

  const openResult = useCallback((item) => {
    if (!item) return;
    navigate(item.to);
    closeSearch();
  }, [closeSearch, navigate]);

  useEffect(() => {
    if (!open) return undefined;
    const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
    const onKeyDown = (event) => {
      if (event.key === 'Escape') closeSearch();
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        setActiveIndex((index) => Math.min(index + 1, results.length - 1));
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        setActiveIndex((index) => Math.max(index - 1, 0));
      }
      if (event.key === 'Enter' && results[activeIndex]) {
        event.preventDefault();
        openResult(results[activeIndex]);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [activeIndex, closeSearch, open, openResult, results]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[70] bg-slate-950/35 p-3 pt-[9vh] backdrop-blur-[2px]"
      onMouseDown={(event) => event.target === event.currentTarget && closeSearch()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Quick navigation"
        className="mx-auto max-w-2xl overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl motion-safe:animate-[kinetic-dialog-in_150ms_ease-out]"
      >
        <div className="flex items-center gap-3 border-b border-slate-200 px-4">
          <Search className="shrink-0 text-slate-400" size={20} />
          <input
            ref={inputRef}
            role="combobox"
            aria-label="Quick navigation"
            aria-autocomplete="list"
            aria-controls="quick-navigation-results"
            aria-expanded="true"
            aria-activedescendant={results[activeIndex] ? `quick-nav-${activeIndex}` : undefined}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActiveIndex(0);
            }}
            placeholder="Jump to People, Time off, Files, Goals, or Settings…"
            className="h-14 min-w-0 flex-1 bg-transparent text-base text-slate-900 outline-none placeholder:text-slate-400"
          />
          <button
            type="button"
            onClick={closeSearch}
            className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close quick navigation"
          >
            <X size={17} />
          </button>
        </div>
        <div id="quick-navigation-results" role="listbox" className="max-h-[56vh] overflow-y-auto p-2">
          <p className="px-3 pb-2 pt-1 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400">
            {query ? 'Matching destinations' : 'Quick navigation'}
          </p>
          {results.length === 0 ? (
            <div className="px-4 py-10 text-center">
              <p className="text-sm font-semibold text-slate-800">No matching destination</p>
              <p className="mt-1 text-sm text-slate-500">Try a page name such as People, Time off, Files, Goals, or Settings.</p>
            </div>
          ) : results.map(({ to, label, group, icon: Icon }, index) => (
            <button
              id={`quick-nav-${index}`}
              key={to}
              type="button"
              role="option"
              aria-selected={activeIndex === index}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => openResult(results[index])}
              className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left focus:outline-none ${activeIndex === index ? 'bg-blue-50' : 'hover:bg-blue-50'}`}
            >
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600 group-hover:border-blue-200 group-hover:text-blue-700">
                <Icon size={17} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-slate-900">{label}</span>
                <span className="block text-xs text-slate-500">{group}</span>
              </span>
              <ArrowRight size={15} className="text-slate-300 group-hover:text-blue-600" />
            </button>
          ))}
        </div>
        <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-4 py-2 text-[11px] text-slate-500">
          <span>Use ↑ ↓ to choose and Enter to open</span>
          <span className="rounded border border-slate-300 bg-white px-1.5 py-0.5 font-semibold">Esc</span>
        </div>
      </div>
    </div>
  );
}
