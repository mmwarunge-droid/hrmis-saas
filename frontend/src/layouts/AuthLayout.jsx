import {
  BarChart3,
  Building2,
  CheckCircle2,
  Network,
  ShieldCheck,
  Sparkles,
  UserRoundCheck,
  UsersRound,
  Workflow,
} from 'lucide-react';
import { Outlet } from 'react-router-dom';

const featureCards = [
  {
    icon: Network,
    title: 'Living org structure',
    description: 'See teams, reporting lines and roles at a glance.',
  },
  {
    icon: BarChart3,
    title: 'People analytics',
    description: 'Turn workforce data into clear operational signals.',
  },
  {
    icon: CheckCircle2,
    title: 'Guided workflows',
    description: 'Move onboarding, leave and approvals forward.',
  },
  {
    icon: ShieldCheck,
    title: 'Secure by design',
    description: 'Tenant isolation, MFA and least-privilege access.',
  },
];

const workflowNodes = [
  {
    icon: UsersRound,
    label: 'People directory',
    detail: 'Employee records',
  },
  {
    icon: Building2,
    label: 'Org structure',
    detail: 'Teams and reporting',
  },
  {
    icon: Workflow,
    label: 'Workflows',
    detail: 'Onboarding and leave',
  },
  {
    icon: UserRoundCheck,
    label: 'Secure access',
    detail: 'Roles and identity',
  },
];

function OperationsInfographic() {
  return (
    <div
      aria-label="Connected people operations"
      className="relative my-8 hidden 2xl:block"
    >
      <div className="absolute left-[12.5%] right-[12.5%] top-8 h-px bg-gradient-to-r from-transparent via-cyan-300/50 to-transparent" />

      <div className="relative grid grid-cols-4 gap-3">
        {workflowNodes.map(({ icon: Icon, label, detail }, index) => (
          <div key={label} className="relative text-center">
            {index < workflowNodes.length - 1 && (
              <span
                aria-hidden="true"
                className="absolute left-[calc(50%+2rem)] right-[-50%] top-8 border-t border-dashed border-cyan-300/30"
              />
            )}

            <div className="relative mx-auto grid h-16 w-16 place-items-center rounded-2xl border border-cyan-200/20 bg-cyan-300/10 text-cyan-200 shadow-[0_18px_45px_rgba(8,145,178,0.12)] backdrop-blur">
              <Icon size={25} strokeWidth={1.8} />
            </div>

            <p className="mt-3 text-sm font-bold text-white">{label}</p>
            <p className="mt-1 text-xs leading-5 text-slate-400">{detail}</p>
          </div>
        ))}
      </div>

      <div className="mx-auto mt-6 flex max-w-xl items-center justify-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-3 text-xs text-slate-300 backdrop-blur">
        <Sparkles className="shrink-0 text-cyan-300" size={16} />
        <span>
          One operational record connects every employee, decision and workflow.
        </span>
      </div>
    </div>
  );
}

export default function AuthLayout() {
  return (
    <main className="min-h-dvh bg-slate-950 xl:grid xl:grid-cols-[minmax(420px,0.78fr)_minmax(0,1.22fr)]">
      <section className="relative grid min-h-dvh place-items-center overflow-hidden bg-slate-50 px-4 py-8 sm:px-8 sm:py-10">
        <div className="absolute -left-32 top-16 h-72 w-72 rounded-full bg-cyan-200/40 blur-3xl" />
        <div className="absolute -bottom-28 right-0 h-72 w-72 rounded-full bg-violet-200/40 blur-3xl" />

        <div className="relative w-full max-w-md">
          <div className="mb-7 flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-700 text-white shadow-lg">
              <Sparkles size={20} />
            </span>

            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-700">
                People OS
              </p>
              <p className="font-bold text-slate-950">HRMIS</p>
            </div>
          </div>

          <Outlet />
        </div>
      </section>

      <section className="relative hidden min-h-dvh overflow-y-auto bg-gradient-to-br from-slate-950 via-blue-950 to-cyan-950 p-10 text-white xl:flex xl:flex-col 2xl:p-12">
        <div className="absolute -right-20 -top-20 h-80 w-80 rounded-full bg-cyan-400/20 blur-3xl" />
        <div className="absolute bottom-20 left-10 h-64 w-64 rounded-full bg-violet-500/15 blur-3xl" />

        <div className="relative">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-cyan-300">
            Modern people operations
          </p>

          <h1 className="mt-6 max-w-2xl text-5xl font-bold leading-[1.08] tracking-tight">
            One connected home for people, time, documents and decisions.
          </h1>

          <p className="mt-5 max-w-xl text-base leading-7 text-slate-300">
            A people-first workspace with the operational depth administrators
            need and the clarity employees expect.
          </p>
        </div>

        <OperationsInfographic />

        <div className="relative mt-auto grid grid-cols-2 gap-4 pt-8 2xl:pt-0">
          {featureCards.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur transition duration-200 hover:-translate-y-0.5 hover:border-cyan-300/20 hover:bg-white/[0.07]"
            >
              <Icon className="text-cyan-300" size={22} />
              <h2 className="mt-4 font-bold">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                {description}
              </p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}