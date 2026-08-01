import { Inbox } from 'lucide-react';

export default function EmptyState({ title = 'Nothing here yet', description = 'New activity will appear here.', action, icon: Icon = Inbox }) {
  return (
    <div className="grid min-h-48 place-items-center rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-7 text-center">
      <div>
        <span className="mx-auto grid h-11 w-11 place-items-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm">
          <Icon size={19} />
        </span>
        <h3 className="mt-3 text-sm font-bold text-slate-900">{title}</h3>
        <p className="mx-auto mt-1 max-w-sm text-sm leading-6 text-slate-500">{description}</p>
        {action && <div className="mt-4">{action}</div>}
      </div>
    </div>
  );
}
