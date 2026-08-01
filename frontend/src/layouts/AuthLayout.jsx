import {
  BarChart3,
  Building2,
  CheckCircle2,
  Network,
  ShieldCheck,
  UserRoundCheck,
  UsersRound,
  Workflow,
} from 'lucide-react';
import { Outlet } from 'react-router-dom';
import KineticLogo from '../components/ui/KineticLogo.jsx';

const featureCards = [
  { icon: Network, title: 'Living org structure', description: 'See teams, reporting lines and roles at a glance.' },
  { icon: BarChart3, title: 'People analytics', description: 'Turn workforce data into clear operational signals.' },
  { icon: CheckCircle2, title: 'Guided workflows', description: 'Move onboarding, leave and approvals forward.' },
  { icon: ShieldCheck, title: 'Secure by design', description: 'Tenant isolation, MFA and least-privilege access.' },
];

const workflowNodes = [
  { icon: UsersRound, label: 'People directory', detail: 'Employee records' },
  { icon: Building2, label: 'Org structure', detail: 'Teams and reporting' },
  { icon: Workflow, label: 'Workflows', detail: 'Onboarding and time off' },
  { icon: UserRoundCheck, label: 'Secure access', detail: 'Roles and identity' },
];

function OperationsInfographic() {
  return (
    <div aria-label="Connected people operations" className="relative my-10 hidden 2xl:block">
      <div className="absolute left-[12.5%] right-[12.5%] top-7 h-px bg-blue-400/30" />
      <div className="relative grid grid-cols-4 gap-4">
        {workflowNodes.map(({ icon: Icon, label, detail }) => (
          <div key={label} className="text-center">
            <div className="relative mx-auto grid h-14 w-14 place-items-center rounded-xl border border-white/15 bg-white/10 text-blue-100 shadow-lg backdrop-blur">
              <Icon size={22} strokeWidth={1.8} />
            </div>
            <p className="mt-3 text-sm font-bold text-white">{label}</p>
            <p className="mt-1 text-xs leading-5 text-blue-100/65">{detail}</p>
          </div>
        ))}
      </div>
      <div className="mx-auto mt-7 max-w-lg rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-center text-xs text-blue-100/75 backdrop-blur">
        One operational record connects every employee, decision and workflow.
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
          <p className="mt-6 text-center text-[11px] text-slate-400">© {new Date().getFullYear()} Kinetic. Secure people operations.</p>
        </div>
      </section>

      <section className="relative hidden min-h-dvh overflow-y-auto bg-gradient-to-br from-blue-950 via-blue-900 to-slate-950 p-10 text-white xl:flex xl:flex-col 2xl:p-12">
        <div className="absolute -right-20 -top-20 h-80 w-80 rounded-full bg-blue-400/20 blur-3xl" />
        <div className="absolute bottom-20 left-10 h-64 w-64 rounded-full bg-sky-500/10 blur-3xl" />
        <div className="relative">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-blue-200">Modern people operations</p>
          <h1 className="mt-5 max-w-2xl text-5xl font-bold leading-[1.08] tracking-[-0.035em]">
            One connected home for people, time, files, and decisions.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-blue-100/70">
            An employee-first workspace with the operational depth administrators need and the clarity every team expects.
          </p>
        </div>

        <OperationsInfographic />

        <div className="relative mt-auto grid grid-cols-2 gap-3 pt-8 2xl:pt-0">
          {featureCards.map(({ icon: Icon, title, description }) => (
            <div key={title} className="rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur transition hover:border-white/20 hover:bg-white/[0.08]">
              <Icon className="text-blue-200" size={20} />
              <h2 className="mt-3 text-sm font-bold">{title}</h2>
              <p className="mt-1.5 text-xs leading-5 text-blue-100/60">{description}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
