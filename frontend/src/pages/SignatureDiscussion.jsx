import { ArrowLeft, ShieldCheck } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import SignatureDiscussionPanel from '../components/signatures/SignatureDiscussionPanel.jsx';

export default function SignatureDiscussion() {
  const { recipientId } = useParams();

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-8">
      <div className="mx-auto max-w-3xl">
        <Link
          to="/tasks"
          className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-950"
        >
          <ArrowLeft size={16} />
          Back to tasks
        </Link>

        <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-start gap-3">
            <ShieldCheck
              size={22}
              className="mt-0.5 shrink-0 text-blue-700"
            />
            <div>
              <h1 className="text-xl font-bold text-slate-950">
                Document discussion
              </h1>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                You were invited into this clarification thread.
                Participation here does not grant access to the
                underlying document or signing controls.
              </p>
            </div>
          </div>

          <div className="mt-6">
            <SignatureDiscussionPanel
              recipientId={recipientId}
              compact
            />
          </div>
        </section>
      </div>
    </main>
  );
}
