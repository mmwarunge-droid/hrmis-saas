import { ArrowDownRight, ArrowUpRight } from 'lucide-react';
import Skeleton from './Skeleton.jsx';

export default function StatCard({ label, value, detail, icon: Icon, tone = 'blue', trend, loading = false }) {
  const tones = {
    blue: 'border-blue-100 bg-blue-50 text-blue-700',
    violet: 'border-blue-100 bg-blue-50 text-blue-700',
    emerald: 'border-emerald-100 bg-emerald-50 text-emerald-700',
    amber: 'border-amber-100 bg-amber-50 text-amber-700',
    rose: 'border-rose-100 bg-rose-50 text-rose-700',
    slate: 'border-slate-200 bg-slate-100 text-slate-700',
  };
  const trendValue = typeof trend === 'object' ? trend.value : trend;
  const trendDirection = typeof trend === 'object' ? trend.direction : 'up';
  const TrendIcon = trendDirection === 'down' ? ArrowDownRight : ArrowUpRight;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)] md:p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold text-slate-500">{label}</p>
          {loading ? (
            <Skeleton className="mt-2 h-8 w-24" />
          ) : (
            <p className="mt-2 text-[28px] font-bold leading-none tracking-[-0.035em] text-slate-950">{value}</p>
          )}
        </div>
        {Icon && (
          <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg border ${tones[tone] || tones.blue}`}>
            <Icon size={18} />
          </span>
        )}
      </div>
      {(detail || trendValue || loading) && (
        <div className="mt-3 flex min-h-5 items-center gap-2 text-xs">
          {loading ? <Skeleton className="h-4 w-36" /> : (
            <>
              {trendValue && (
                <span className={`inline-flex items-center gap-0.5 font-semibold ${trendDirection === 'down' ? 'text-red-600' : 'text-emerald-600'}`}>
                  <TrendIcon size={13} /> {trendValue}
                </span>
              )}
              {detail && <span className="truncate text-slate-500">{detail}</span>}
            </>
          )}
        </div>
      )}
    </section>
  );
}
