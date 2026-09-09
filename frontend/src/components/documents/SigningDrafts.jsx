import { useContext, useEffect, useState } from 'react';
import { AuthContext } from '../../context/AuthContext.jsx';
import { formDraftApi } from '../../api/formDraftApi.js';
import { documentApi } from '../../api/documentApi.js';
import WorkflowFeedback from '../forms/WorkflowFeedback.jsx';
import { errorState } from '../../utils/formFeedback.js';

export default function SigningDrafts({ refreshKey, onOpen }) {
  const auth = useContext(AuthContext);
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!auth?.user) return;
    let active = true;
    formDraftApi.list(auth.user.id).then(({ data }) => { if (active) setItems(data.items.filter((item) => item.key.startsWith('signing.'))); })
      .catch((err) => { if (active) setError(err); });
    return () => { active = false; };
  }, [auth?.user, refreshKey]);
  if (!items.length && !error) return null;
  return <section className="space-y-3 rounded-lg border p-4" aria-label="Saved signing drafts">
    <h2 className="font-semibold">Your signing drafts</h2>
    <p className="text-sm text-slate-600">Private preparation drafts. No invitations have been sent.</p>
    <WorkflowFeedback state={error ? errorState(error) : null} />
    {items.map((item) => <div key={item.key} className="flex flex-wrap items-center justify-between gap-3 text-sm">
      <span>{item.title} · Draft · {new Date(item.updated_at).toLocaleString()}</span>
      <button type="button" className="underline" disabled={busy} onClick={async () => {
        setBusy(true); setError(null);
        try { const { data } = await documentApi.get(item.key.slice('signing.'.length)); onOpen(data); }
        catch (err) { setError(err); } finally { setBusy(false); }
      }}>Open draft</button>
    </div>)}
  </section>;
}
