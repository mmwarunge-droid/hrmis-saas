import {
  BookOpen,
  CalendarDays,
  FileText,
  LifeBuoy,
  LockKeyhole,
  Target,
  Users,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import Card from '../components/ui/Card.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';

const topics = [
  {
    icon: Users,
    title: 'People and access',
    description: 'Create employee records, link user accounts and maintain least-privilege roles.',
    to: '/employees',
  },
  {
    icon: CalendarDays,
    title: 'Time off',
    description: 'Request leave, review approval queues and understand balance activity.',
    to: '/leave',
  },
  {
    icon: FileText,
    title: 'Files and signatures',
    description: 'Upload documents, track acknowledgements and review signature evidence.',
    to: '/documents',
  },
  {
    icon: Target,
    title: 'Goals and KPIs',
    description: 'Create measurable goals, record check-ins and monitor goal health.',
    to: '/goals',
  },
  {
    icon: LockKeyhole,
    title: 'Security',
    description: 'Review MFA, account recovery and secure session behavior.',
    to: '/settings',
  },
];

export default function HelpCenter() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Support"
        title="Kinetic help center"
        description="Practical guidance for the workflows used in the demo and day-to-day people operations."
      />

      <Card className="border-blue-200 bg-gradient-to-br from-blue-50 to-white">
        <div className="flex items-start gap-4">
          <span className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-blue-700 text-white">
            <LifeBuoy size={22} />
          </span>
          <div>
            <h2 className="text-lg font-bold text-slate-950">Need a guided walkthrough?</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              Use Quick navigation with Ctrl or Command + K to jump between modules. The deterministic demo guide in the repository contains the role matrix, scenarios and reset procedure.
            </p>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {topics.map(({ icon: Icon, title, description, to }) => (
          <Link key={title} to={to} className="group">
            <Card className="h-full transition group-hover:-translate-y-0.5 group-hover:border-blue-200 group-hover:shadow-md">
              <span className="grid h-10 w-10 place-items-center rounded-lg bg-blue-50 text-blue-700">
                <Icon size={19} />
              </span>
              <h2 className="mt-4 font-bold text-slate-950">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
            </Card>
          </Link>
        ))}
      </div>

      <Card>
        <div className="flex items-center gap-3">
          <BookOpen className="text-blue-700" size={20} />
          <div>
            <p className="font-bold text-slate-950">Demo operating guide</p>
            <p className="mt-1 text-sm text-slate-600">
              Repository operators should follow docs/DEMO_ENVIRONMENT.md for credentials, MFA codes, reset safety and presentation checks.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
