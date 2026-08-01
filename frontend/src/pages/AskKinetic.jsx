import { useEffect, useState } from 'react';
import { ArrowLeft, Bot, ExternalLink, FileText, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';

import { employeeHomeApi } from '../api/employeeHomeApi.js';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import Skeleton from '../components/ui/Skeleton.jsx';

export default function AskKinetic() {
  const [assistant, setAssistant] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    employeeHomeApi.get()
      .then((response) => {
        if (active) setAssistant(response.data.assistant);
      })
      .catch((err) => {
        if (active) setError(err.error?.message || 'Unable to load Ask Kinetic.');
      });
    return () => { active = false; };
  }, []);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Link to="/dashboard" className="inline-flex items-center gap-2 text-sm font-semibold text-blue-700 hover:text-blue-900">
        <ArrowLeft size={16} /> Back home
      </Link>
      <PageHeader
        eyebrow="Employee help"
        title="Ask Kinetic"
        description="Open your organization-approved guidance assistant or find the right trusted resource."
      />
      {error && <Alert type="error">{error}</Alert>}

      <Card padded={false} className="overflow-hidden">
        <div className="grid lg:grid-cols-[1.15fr_0.85fr]">
          <div className="bg-gradient-to-br from-blue-800 via-blue-700 to-blue-950 p-6 text-white md:p-8">
            <span className="grid h-12 w-12 place-items-center rounded-xl border border-white/15 bg-white/10">
              <Bot size={23} />
            </span>
            <p className="mt-6 text-xs font-bold uppercase tracking-[0.18em] text-blue-200">Approved guidance</p>
            <h2 className="mt-2 max-w-xl text-3xl font-bold tracking-[-0.025em]">Get help with everyday workplace questions.</h2>
            <p className="mt-3 max-w-xl text-sm leading-6 text-blue-100/80">
              Ask Kinetic connects employees to organization-approved guidance. It does not make employment, payroll, disciplinary, medical, or legal decisions.
            </p>
          </div>

          <div className="flex min-h-72 items-center p-6 md:p-8">
            <div className="w-full">
              {!assistant && !error ? (
                <div className="space-y-3"><Skeleton className="h-5 w-40" /><Skeleton lines={3} /><Skeleton className="h-10 w-40" /></div>
              ) : assistant?.enabled && assistant?.url ? (
                <>
                  <p className="text-sm font-bold text-slate-950">Your assistant is ready</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">The assistant opens in a separate, organization-approved workspace.</p>
                  <a href={assistant.url} target="_blank" rel="noreferrer" className="mt-5 inline-flex">
                    <Button size="lg">Open Ask Kinetic <ExternalLink size={16} /></Button>
                  </a>
                </>
              ) : assistant ? (
                <>
                  <p className="text-sm font-bold text-slate-950">Ask Kinetic is not configured yet</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">
                    An organization administrator can connect an approved employee-help tool in Employee experience settings. Until then, use Files or contact HR.
                  </p>
                  <Link to="/documents" className="mt-5 inline-flex"><Button variant="secondary">Open files</Button></Link>
                </>
              ) : null}
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <span className="grid h-10 w-10 place-items-center rounded-lg border border-blue-100 bg-blue-50 text-blue-700"><FileText size={19} /></span>
          <h2 className="mt-4 text-base font-bold text-slate-950">Use approved resources</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">Company policies, training resources, and recommended documents remain available from your homepage and Files.</p>
          <Link to="/documents" className="mt-4 inline-flex text-sm font-semibold text-blue-700 hover:text-blue-900">Open files</Link>
        </Card>
        <Card>
          <span className="grid h-10 w-10 place-items-center rounded-lg border border-emerald-100 bg-emerald-50 text-emerald-700"><ShieldCheck size={19} /></span>
          <h2 className="mt-4 text-base font-bold text-slate-950">Escalate sensitive questions</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">Questions about individual pay, discipline, medical information, or employment decisions should be handled by an authorized HR contact.</p>
        </Card>
      </div>
    </div>
  );
}
