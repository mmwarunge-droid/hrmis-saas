export default function Table({ columns, rows, empty = 'No records found.', onRowClick }) {
  return (
    <div className="overflow-x-auto rounded-3xl border border-slate-200/80 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-100 text-sm">
        <thead className="bg-slate-50/80"><tr>{columns.map((c) => <th key={c.key} className="px-5 py-4 text-left text-xs font-bold uppercase tracking-wider text-slate-500">{c.label}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">
          {rows.length === 0 ? <tr><td colSpan={columns.length} className="px-5 py-12 text-center text-slate-500">{empty}</td></tr> : rows.map((row, idx) => (
            <tr key={row.id || idx} onClick={() => onRowClick?.(row)} className={onRowClick ? 'cursor-pointer transition hover:bg-cyan-50/40' : 'transition hover:bg-slate-50/60'}>
              {columns.map((c) => <td key={c.key} className="px-5 py-4 text-slate-700">{c.render ? c.render(row) : row[c.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
