import { ChevronLeft, ChevronRight } from 'lucide-react';
import Button from './Button.jsx';

export default function Pagination({ page, pageSize, total, onPageChange, label = 'items' }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const current = Math.min(Math.max(page, 1), totalPages);
  const start = total === 0 ? 0 : ((current - 1) * pageSize) + 1;
  const end = Math.min(current * pageSize, total);

  return (
    <div className="flex flex-col gap-3 border-t border-slate-200 px-4 py-3 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
      <p>{start}–{end} of {total} {label}</p>
      <div className="flex items-center gap-2">
        <Button size="sm" variant="secondary" className="px-2" disabled={current <= 1} onClick={() => onPageChange(current - 1)} aria-label="Previous page">
          <ChevronLeft size={15} />
        </Button>
        <span className="min-w-20 text-center font-semibold text-slate-700">Page {current} of {totalPages}</span>
        <Button size="sm" variant="secondary" className="px-2" disabled={current >= totalPages} onClick={() => onPageChange(current + 1)} aria-label="Next page">
          <ChevronRight size={15} />
        </Button>
      </div>
    </div>
  );
}
