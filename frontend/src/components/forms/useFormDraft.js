import { useContext, useEffect, useRef, useState } from 'react';
import { AuthContext } from '../../context/AuthContext.jsx';
import { formDraftApi } from '../../api/formDraftApi.js';

export function draftSnapshot(data) {
  return JSON.stringify(data, (key, value) => {
    if (/password|secret|token|otp|recovery.?code|signature_image/i.test(key)) return undefined;
    if (typeof File !== 'undefined' && value instanceof File) return null;
    if (typeof value === 'string' && value.startsWith('data:')) return undefined;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return Object.fromEntries(Object.keys(value).sort().map((name) => [name, value[name]]));
    }
    return value;
  });
}
export default function useFormDraft(config, { paused = false } = {}) {
  const auth = useContext(AuthContext);
  const enabled = Boolean(auth?.user && config?.key);
  const latest = useRef(config); latest.current = config;
  const state = useRef({ revision: 0, saved: null, ready: false });
  const queue = useRef(Promise.resolve());
  const initialSnapshot = useRef(draftSnapshot(config?.data));
  const completedSnapshot = useRef(null);
  const generation = useRef(0);
  const [ready, setReady] = useState(false);
  const [candidate, setCandidate] = useState(null);
  const [status, setStatus] = useState('');
  const [failure, setFailure] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    formDraftApi.get(config.key, auth.user.id).then(({ data }) => {
      if (!active) return;
      state.current.ready = true; setReady(true);
      if (data?.key) { state.current.revision = data.revision; setCandidate(data); }
    }).catch((error) => { if (active) setFailure(error); });
    return () => { active = false; };
  }, [enabled, config?.key, auth?.user?.id]);
  const save = () => {
    const snapshot = draftSnapshot(latest.current?.data);
    const savingGeneration = generation.current;
    const key = latest.current?.key;
    const title = latest.current?.title || key;
    const work = queue.current.catch(() => {}).then(async () => {
      if (!enabled || savingGeneration !== generation.current) return false;
      if (!state.current.ready) throw new Error('Draft storage is unavailable. Reload saved drafts and try again.');
      if (candidate) throw new Error('Resume or discard the saved draft before saving your current entries.');
      setBusy(true); setFailure(null);
      try {
        const { data } = await formDraftApi.save(key, { title, revision: state.current.revision, data: JSON.parse(snapshot) }, auth.user.id);
        state.current.revision = data.revision; state.current.saved = snapshot;
        setStatus(`Draft saved ${new Date(data.updated_at).toLocaleString()}`);
        return snapshot === draftSnapshot(latest.current?.data);
      } finally { setBusy(false); }
    });
    queue.current = work;
    return work.catch((error) => { setFailure(error); return false; });
  };
  const discard = async () => {
    generation.current += 1;
    initialSnapshot.current = draftSnapshot(latest.current?.data);
    await queue.current.catch(() => {});
    try {
      if (state.current.revision) await formDraftApi.discard(latest.current.key, state.current.revision, auth.user.id);
      state.current.revision = 0; state.current.saved = null;
      setCandidate(null); setStatus('Draft discarded'); setFailure(null);
      return true;
    } catch (error) { setFailure(error); return false; }
  };
  const complete = async () => {
    completedSnapshot.current = draftSnapshot(latest.current?.data);
    const cleared = await discard();
    if (cleared) setStatus('Draft cleared after submission.');
    return cleared;
  };
  const resume = () => {
    latest.current.onRestore(candidate.data);
    state.current.saved = draftSnapshot(candidate.data);
    setStatus(`Resumed draft saved ${new Date(candidate.updated_at).toLocaleString()}`);
    setCandidate(null);
  };
  const reload = async () => {
    setFailure(null);
    try {
      const { data } = await formDraftApi.get(latest.current.key, auth.user.id);
      state.current.ready = true; setReady(true);
      state.current.revision = data?.revision || 0;
      setCandidate(data?.key ? data : null);
    } catch (error) { setFailure(error); }
  };
  const snapshot = draftSnapshot(config?.data);
  useEffect(() => {
    if (!enabled || !ready || candidate || busy || failure || paused || config?.autoSave === false
      || (state.current.saved === null && (snapshot === initialSnapshot.current || snapshot === completedSnapshot.current)) || snapshot === state.current.saved) return;
    const timer = window.setTimeout(() => { save(); }, 1200);
    return () => window.clearTimeout(timer);
  // Snapshot is the controlled form state; save reads the latest config and revision.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshot, enabled, ready, candidate, busy, failure, paused, config?.autoSave]);
  const displayStatus = state.current.saved && state.current.saved !== draftSnapshot(config?.data)
    ? `${status} · New changes are not saved.` : status;
  return { enabled, autoSave: config?.autoSave !== false, isSaved: state.current.saved !== null && state.current.saved === draftSnapshot(config?.data), candidate, status: displayStatus, failure, busy, save, discard, complete, resume, reload };
}
