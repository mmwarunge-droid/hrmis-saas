import {
  BarChart3,
  Building2,
  CheckCircle2,
  Globe2,
  Network,
  ShieldCheck,
  Sparkles,
  UsersRound,
  Workflow,
} from 'lucide-react';
import { Outlet } from 'react-router-dom';
import KineticLogo from '../components/ui/KineticLogo.jsx';

const featureCards = [
  { icon: Network, title: 'Connected teams', description: 'Keep people, reporting lines and workflows in one shared operating system.' },
  { icon: BarChart3, title: 'Clear people signals', description: 'Turn workforce activity into useful operational insight.' },
  { icon: CheckCircle2, title: 'Work that keeps moving', description: 'Guide onboarding, leave and approvals without losing momentum.' },
  { icon: ShieldCheck, title: 'Enterprise foundations', description: 'Secure access, tenant isolation and role-aware controls by design.' },
];

const workflowNodes = [
  { icon: UsersRound, label: 'People', detail: 'Employee records' },
  { icon: Building2, label: 'Structure', detail: 'Teams and reporting' },
  { icon: Workflow, label: 'Workflows', detail: 'Onboarding and time off' },
  { icon: Globe2, label: 'Momentum', detail: 'Built for African teams' },
];

function OperationsInfographic() {
  return (
    <div aria-label="Connected people operations" className="relative mt-8 hidden 2xl:block">
      <div className="absolute left-[12.5%] right-[12.5%] top-7 h-px bg-blue-300/25" />
      <div className="relative grid grid-cols-4 gap-4">
        {workflowNodes.map(({ icon: Icon, label, detail }) => (
          <div key={label} className="text-center">
            <div className="relative mx-auto grid h-14 w-14 place-items-center rounded-xl border border-white/15 bg-white/10 text-blue-100 shadow-lg backdrop-blur-md">
              <Icon size={22} strokeWidth={1.8} />
            </div>
            <p className="mt-3 text-sm font-bold text-white">{label}</p>
            <p className="mt-1 text-xs leading-5 text-blue-100/75">{detail}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AuthLayout() {
  return (
    <main className="min-h-dvh bg-blue-950 xl:grid xl:grid-cols-[minmax(420px,0.78fr)_minmax(0,1.22fr)]">
      <section className="relative grid min-h-dvh place-items-center overflow-hidden bg-slate-50 px-4 py-8 sm:px-8 sm:py-10">
        <div className="absolute -left-24 top-10 h-64 w-64 rounded-full bg-blue-100/70 blur-3xl" />
        <div className="absolute -bottom-20 right-0 h-64 w-64 rounded-full bg-sky-100/70 blur-3xl" />
        <div className="relative w-full max-w-md">
          <div className="mb-7"><KineticLogo /></div>
          <Outlet />
          <p className="mt-6 text-center text-[11px] text-slate-500">© {new Date().getFullYear()} Kinetic. Secure people operations.</p>
        </div>
      </section>

      <section className="relative hidden min-h-dvh overflow-hidden bg-blue-950 text-white xl:block">
        <div className="absolute inset-0" aria-hidden="true">
          <img
            src="/kinetic-africa-hero-1.png"
            alt=""
            className="kinetic-auth-hero kinetic-auth-hero-primary absolute inset-0 h-full w-full object-cover object-center"
          />
          <img
            src="/kinetic-africa-hero-2.png"
            alt=""
            className="kinetic-auth-hero kinetic-auth-hero-secondary absolute inset-0 h-full w-full object-cover object-center"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-blue-950 via-blue-950/75 to-blue-950/20" />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-transparent to-blue-950/20" />
          <div className="kinetic-auth-orb absolute -right-20 top-16 h-72 w-72 rounded-full bg-sky-400/20 blur-3xl" />
          <div className="kinetic-auth-orb kinetic-auth-orb-delayed absolute bottom-24 left-1/3 h-52 w-52 rounded-full bg-blue-500/20 blur-3xl" />
        </div>

        <div className="relative z-10 flex min-h-dvh flex-col p-10 2xl:p-12">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-blue-100 backdrop-blur-md">
              <Sparkles size={14} aria-hidden="true" />
              Built for ambitious African teams
            </div>
            <h1 className="mt-5 max-w-xl text-5xl font-bold leading-[1.05] tracking-[-0.04em] 2xl:text-[3.6rem]">
              People in motion. Teams in sync. Growth with momentum.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-blue-50/85">
              Kinetic brings people operations, culture and performance into one modern workspace—corporate enough for administrators and human enough for everyone else.
            </p>
          </div>

          <OperationsInfographic />

          <div className="mt-auto grid max-w-3xl grid-cols-2 gap-3 pt-8">
            {featureCards.map(({ icon: Icon, title, description }) => (
              <div key={title} className="rounded-xl border border-white/15 bg-blue-950/35 p-4 shadow-xl backdrop-blur-md transition hover:border-white/25 hover:bg-blue-900/45">
                <Icon className="text-sky-200" size={20} />
                <h2 className="mt-3 text-sm font-bold">{title}</h2>
                <p className="mt-1.5 text-xs leading-5 text-blue-50/75">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
