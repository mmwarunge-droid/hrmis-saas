import { useEffect, useState } from 'react';
import { ArrowLeft, Bot, ExternalLink, FileText, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';

import { employeeHomeApi } from '../api/employeeHomeApi.js';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';

export default function AskAce() {
  const [assistant, setAssistant] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    employeeHomeApi.get()
      .then((response) => {
        if (active) setAssistant(response.data.assistant);
      })
      .catch((err) => {
        if (active) setError(err.error?.message || 'Unable to load Ask ACE.');
      });
    return () => { active = false; };
  }, []);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link to="/dashboard" className="inline-flex items-center gap-2 text-sm font-semibold text-cyan-800">
        <ArrowLeft size={16} /> Back home
      </Link>
      {error && <Alert type="error">{error}</Alert>}

      <Card className="overflow-hidden bg-gradient-to-br from-slate-950 via-violet-950 to-cyan-950 text-white">
        <span className="grid h-14 w-14 place-items-center rounded-2xl bg-white/10 ring-1 ring-white/15">
          <Bot size={26} />
        </span>
        <p className="mt-6 text-xs font-bold uppercase tracking-[0.22em] text-cyan-200">Ask ACE</p>
        <h1 className="mt-2 text-3xl font-bold">Get help with workplace questions</h1>
        <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-200">
          Ask ACE is designed to connect employees to organization-approved guidance. It does not make employment, payroll, disciplinary or legal decisions.
        </p>

        <div className="mt-8">
          {assistant?.enabled && assistant?.url ? (
            <a href={assistant.url} target="_blank" rel="noreferrer">
              <Button variant="accent" size="lg">
                Open Ask ACE <ExternalLink size={17} />
              </Button>
            </a>
          ) : assistant ? (
            <div className="rounded-2xl border border-white/10 bg-white/10 p-5">
              <p className="font-semibold">Ask ACE is not configured yet.</p>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Your organization administrator can connect an approved employee-help tool from Employee experience settings. Until then, use Essentials or contact HR.
              </p>
            </div>
          ) : (
            <p className="text-sm text-slate-300">Loading your organization’s assistant settings…</p>
          )}
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <FileText className="text-cyan-700" size={22} />
          <h2 className="mt-4 font-bold text-slate-950">Use approved resources</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Company policies, training resources and recommended documents remain available from your homepage and Documents.
          </p>
          <Link to="/documents" className="mt-4 inline-flex text-sm font-semibold text-cyan-800">
            Open documents
          </Link>
        </Card>
        <Card>
          <ShieldCheck className="text-emerald-700" size={22} />
          <h2 className="mt-4 font-bold text-slate-950">Escalate sensitive questions</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Questions about individual pay, discipline, medical information or employment decisions should be handled by an authorized HR contact.
          </p>
        </Card>
      </div>
    </div>
  );
}
