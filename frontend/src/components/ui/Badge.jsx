export default function Badge({ children, tone = 'slate', className = '' }) {
  const tones = {
    slate: 'border-slate-200 bg-slate-100 text-slate-700',
    blue: 'border-blue-200 bg-blue-50 text-blue-700',
    cyan: 'border-sky-200 bg-sky-50 text-sky-700',
    green: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-800',
    red: 'border-red-200 bg-red-50 text-red-700',
    violet: 'border-blue-200 bg-blue-50 text-blue-700',
  };
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-semibold capitalize leading-5 ${tones[tone] || tones.slate} ${className}`}>
      {children}
    </span>
  );
}
