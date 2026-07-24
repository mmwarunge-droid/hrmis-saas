import { Sparkles } from 'lucide-react';

export default function EmptyState({ title = 'Nothing here yet', description = 'New activity will appear here.', action }) {
  return (
    <div className="grid min-h-48 place-items-center rounded-3xl border border-dashed border-slate-200 bg-slate-50/70 p-8 text-center">
      <div>
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-white text-cyan-700 shadow-sm"><Sparkles size={20} /></span>
        <h3 className="mt-4 font-semibold text-slate-900">{title}</h3>
        <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>
        {action && <div className="mt-4">{action}</div>}
      </div>
    </div>
  );
}
