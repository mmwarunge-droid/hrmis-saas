import { BarChart3, CheckCircle2, Network, ShieldCheck, Sparkles } from 'lucide-react';
import { Outlet } from 'react-router-dom';

export default function AuthLayout() {
  return (
    <main className="min-h-dvh bg-slate-950 xl:grid xl:grid-cols-[minmax(420px,0.78fr)_minmax(0,1.22fr)]">
      <section className="relative grid min-h-dvh place-items-center overflow-hidden bg-slate-50 px-4 py-8 sm:px-8 sm:py-10">
        <div className="absolute -left-32 top-16 h-72 w-72 rounded-full bg-cyan-200/40 blur-3xl" />
        <div className="absolute -bottom-28 right-0 h-72 w-72 rounded-full bg-violet-200/40 blur-3xl" />
        <div className="relative w-full max-w-md">
          <div className="mb-7 flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-700 text-white shadow-lg"><Sparkles size={20} /></span>
            <div><p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-700">People OS</p><p className="font-bold text-slate-950">HRMIS</p></div>
          </div>
          <Outlet />
        </div>
      </section>

      <section className="relative hidden min-h-dvh overflow-y-auto bg-gradient-to-br from-slate-950 via-blue-950 to-cyan-950 p-10 text-white xl:flex xl:flex-col xl:justify-between 2xl:p-12">
        <div className="absolute -right-20 -top-20 h-80 w-80 rounded-full bg-cyan-400/20 blur-3xl" />
        <div className="absolute bottom-20 left-10 h-64 w-64 rounded-full bg-violet-500/15 blur-3xl" />
        <div className="relative">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-cyan-300">Modern people operations</p>
          <h1 className="mt-6 max-w-2xl text-5xl font-bold leading-[1.08] tracking-tight">One connected home for people, time, documents and decisions.</h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-slate-300">A people-first workspace with the operational depth administrators need and the clarity employees expect.</p>
        </div>
        <div className="relative mt-10 grid grid-cols-2 gap-4">
          {[
            [Network, 'Living org structure', 'See teams, reporting lines and roles at a glance.'],
            [BarChart3, 'People analytics', 'Turn workforce data into clear operational signals.'],
            [CheckCircle2, 'Guided workflows', 'Move onboarding, leave and approvals forward.'],
            [ShieldCheck, 'Secure by design', 'Tenant isolation, MFA and least-privilege access.'],
          ].map(([Icon, title, description]) => (
            <div key={title} className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur">
              <Icon className="text-cyan-300" size={22} />
              <h2 className="mt-4 font-bold">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">{description}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
