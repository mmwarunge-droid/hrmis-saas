export default function StatCard({ label, value, detail, icon: Icon, tone = 'blue', trend }) {
  const tones = {
    blue: 'from-blue-600 to-cyan-500',
    violet: 'from-violet-600 to-fuchsia-500',
    emerald: 'from-emerald-600 to-teal-500',
    amber: 'from-amber-500 to-orange-500',
    rose: 'from-rose-600 to-pink-500',
  };
  return (
    <section className="relative overflow-hidden rounded-3xl border border-white/80 bg-white p-5 shadow-[0_18px_50px_-30px_rgba(15,23,42,0.45)]">
      <div className={`absolute -right-7 -top-7 h-24 w-24 rounded-full bg-gradient-to-br opacity-15 ${tones[tone]}`} />
      <div className="relative flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <p className="mt-3 text-3xl font-bold tracking-tight text-slate-950">{value}</p>
          {detail && <p className="mt-2 text-xs text-slate-500">{detail}</p>}
          {trend && <p className="mt-2 text-xs font-semibold text-emerald-600">{trend}</p>}
        </div>
        {Icon && <span className={`grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br text-white shadow-lg ${tones[tone]}`}><Icon size={20} /></span>}
      </div>
    </section>
  );
}
