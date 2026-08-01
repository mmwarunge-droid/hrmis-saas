import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react';
import { useMemo, useState } from 'react';
import Pagination from './Pagination.jsx';
import Skeleton from './Skeleton.jsx';

function getComparableValue(row, column) {
  if (column.sortValue) return column.sortValue(row);
  return row[column.key];
}

export default function Table({
  columns,
  rows = [],
  empty = 'No records found.',
  onRowClick,
  rowKey = 'id',
  loading = false,
  pageSize = 0,
  density = 'comfortable',
  caption,
}) {
  const [sort, setSort] = useState(null);
  const [page, setPage] = useState(1);

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((item) => item.key === sort.key);
    if (!column) return rows;

    return [...rows].sort((left, right) => {
      const leftValue = getComparableValue(left, column);
      const rightValue = getComparableValue(right, column);
      const result = String(leftValue ?? '').localeCompare(String(rightValue ?? ''), undefined, {
        numeric: true,
        sensitivity: 'base',
      });
      return sort.direction === 'asc' ? result : -result;
    });
  }, [columns, rows, sort]);

  const totalPages = pageSize > 0 ? Math.max(1, Math.ceil(sortedRows.length / pageSize)) : 1;
  const safePage = Math.min(page, totalPages);
  const visibleRows = pageSize > 0
    ? sortedRows.slice((safePage - 1) * pageSize, safePage * pageSize)
    : sortedRows;
  const cellPadding = density === 'compact' ? 'px-4 py-2.5' : 'px-4 py-3.5';

  const toggleSort = (column) => {
    if (!column.sortable) return;
    setPage(1);
    setSort((current) => {
      if (!current || current.key !== column.key) return { key: column.key, direction: 'asc' };
      if (current.direction === 'asc') return { key: column.key, direction: 'desc' };
      return null;
    });
  };

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
      <div className="overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-0 text-sm">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead>
            <tr className="bg-slate-50">
              {columns.map((column) => {
                const isSorted = sort?.key === column.key;
                const ariaSort = !column.sortable
                  ? undefined
                  : isSorted
                    ? (sort.direction === 'asc' ? 'ascending' : 'descending')
                    : 'none';
                return (
                  <th
                    key={column.key}
                    scope="col"
                    aria-sort={ariaSort}
                    className={`sticky top-0 z-[1] border-b border-slate-200 bg-slate-50 px-4 py-3 text-left text-[11px] font-bold uppercase tracking-[0.08em] text-slate-500 ${column.className || ''}`}
                  >
                    {column.sortable ? (
                      <button type="button" className="inline-flex items-center gap-1.5 hover:text-slate-900" onClick={() => toggleSort(column)}>
                        {column.label}
                        {!isSorted && <ChevronsUpDown size={13} />}
                        {isSorted && sort.direction === 'asc' && <ArrowUp size={13} />}
                        {isSorted && sort.direction === 'desc' && <ArrowDown size={13} />}
                      </button>
                    ) : column.label}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 5 }, (_, rowIndex) => (
              <tr key={`loading-${rowIndex}`} className="border-b border-slate-100">
                {columns.map((column) => (
                  <td key={column.key} className={`${cellPadding} border-b border-slate-100`}><Skeleton className="h-4 w-full" /></td>
                ))}
              </tr>
            ))}
            {!loading && visibleRows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-5 py-14 text-center text-sm text-slate-500">{empty}</td>
              </tr>
            )}
            {!loading && visibleRows.map((row, index) => (
              <tr
                key={row[rowKey] || index}
                onClick={() => onRowClick?.(row)}
                onKeyDown={(event) => {
                  if (onRowClick && (event.key === 'Enter' || event.key === ' ')) {
                    event.preventDefault();
                    onRowClick(row);
                  }
                }}
                tabIndex={onRowClick ? 0 : undefined}
                className={`group last:[&>td]:border-b-0 outline-none transition hover:bg-blue-50/40 focus-visible:bg-blue-50 ${onRowClick ? 'cursor-pointer' : ''}`}
              >
                {columns.map((column) => (
                  <td key={column.key} className={`${cellPadding} border-b border-slate-100 text-slate-700 ${column.cellClassName || ''}`}>
                    {column.render ? column.render(row) : (row[column.key] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!loading && pageSize > 0 && sortedRows.length > 0 && (
        <Pagination page={safePage} pageSize={pageSize} total={sortedRows.length} onPageChange={setPage} />
      )}
    </div>
  );
}
