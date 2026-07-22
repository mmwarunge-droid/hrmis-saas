export default function Table({ columns, rows, empty = 'No records found.' }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50"><tr>{columns.map((c) => <th key={c.key} className="px-4 py-3 text-left font-semibold text-slate-600">{c.label}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">
          {rows.length === 0 ? <tr><td colSpan={columns.length} className="px-4 py-8 text-center text-slate-500">{empty}</td></tr> : rows.map((row, idx) => <tr key={row.id || idx}>{columns.map((c) => <td key={c.key} className="px-4 py-3 text-slate-700">{c.render ? c.render(row) : row[c.key]}</td>)}</tr>)}
        </tbody>
      </table>
    </div>
  );
}
