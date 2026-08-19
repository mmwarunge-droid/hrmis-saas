import {
  AtSign,
  MessageSquare,
  Pencil,
  Trash2,
  X,
} from 'lucide-react';
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { signatureApi } from '../../api/signatureApi.js';
import useAuth from '../../hooks/useAuth.js';
import Alert from '../ui/Alert.jsx';
import Badge from '../ui/Badge.jsx';
import Button from '../ui/Button.jsx';

function formatDay(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function trailingMention(text) {
  const match = text.match(/(^|\s)@([A-Za-z0-9._-]{1,80})$/);
  if (!match) return null;

  return {
    query: match[2],
    start: match.index + match[1].length,
  };
}

export default function SignatureDiscussionPanel({
  recipientId,
  allowResolve = false,
  compact = false,
}) {
  const { user } = useAuth();

  const [discussion, setDiscussion] = useState(null);
  const [body, setBody] = useState('');
  const [mentionedUserIds, setMentionedUserIds] = useState([]);
  const [mentionResults, setMentionResults] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const mention = useMemo(
    () => trailingMention(body),
    [body],
  );

  const load = useCallback(async () => {
    const response = await signatureApi.discussion(recipientId);
    setDiscussion(response.data);
  }, [recipientId]);

  useEffect(() => {
    let active = true;

    setLoading(true);
    load()
      .catch((err) => {
        if (!active) return;
        setError(
          err.error?.message
          || 'Unable to load the document discussion.',
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [load]);

  useEffect(() => {
    if (!mention || mention.query.length < 2) {
      setMentionResults([]);
      return undefined;
    }

    let active = true;

    const timer = window.setTimeout(() => {
      signatureApi
        .discussionMentions(recipientId, mention.query)
        .then((response) => {
          if (active) setMentionResults(response.data || []);
        })
        .catch(() => {
          if (active) setMentionResults([]);
        });
    }, 250);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [mention, recipientId]);

  const resetComposer = () => {
    setBody('');
    setMentionedUserIds([]);
    setMentionResults([]);
    setEditingId(null);
  };

  const selectMention = (person) => {
    if (!mention) return;

    setBody(
      `${body.slice(0, mention.start)}@${person.full_name} `,
    );

    setMentionedUserIds((current) => (
      current.includes(person.user_id)
        ? current
        : [...current, person.user_id]
    ));

    setMentionResults([]);
  };

  const submit = async () => {
    const cleanBody = body.trim();
    if (cleanBody.length < 2) return;

    setBusy(true);
    setError('');

    try {
      if (editingId) {
        await signatureApi.updateComment(
          recipientId,
          editingId,
          cleanBody,
          mentionedUserIds,
        );
      } else {
        await signatureApi.comment(
          recipientId,
          cleanBody,
          mentionedUserIds,
        );
      }

      resetComposer();
      await load();
    } catch (err) {
      setError(
        err.error?.message
        || (
          editingId
            ? 'Unable to update comment.'
            : 'Unable to add comment.'
        ),
      );
    } finally {
      setBusy(false);
    }
  };

  const beginEdit = (comment) => {
    setEditingId(comment.id);
    setBody(comment.body || '');
    setMentionedUserIds(
      comment.mentioned_user_ids || [],
    );
    setMentionResults([]);
  };

  const remove = async (comment) => {
    const confirmed = window.confirm(
      'Delete this comment? It will be removed from the conversation, '
      + 'but retained in the security audit history.',
    );

    if (!confirmed) return;

    setBusy(true);
    setError('');

    try {
      await signatureApi.deleteComment(
        recipientId,
        comment.id,
      );

      if (editingId === comment.id) {
        resetComposer();
      }

      await load();
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to delete comment.',
      );
    } finally {
      setBusy(false);
    }
  };

  const resolve = async () => {
    setBusy(true);
    setError('');

    try {
      await signatureApi.resolveDiscussion(recipientId);
      await load();
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to resolve discussion.',
      );
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="text-xs text-slate-500">
        Loading discussion…
      </div>
    );
  }

  return (
    <section
      className={
        compact
          ? ''
          : 'rounded-2xl border border-slate-200 bg-white p-5 shadow-sm'
      }
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 font-bold text-slate-950">
            <MessageSquare size={16} />
            Discussion
          </p>

          <p className="mt-1 text-xs leading-5 text-slate-500">
            Ask a question or use @ to loop a colleague into the
            conversation without granting access to the document.
          </p>
        </div>

        {allowResolve && discussion?.status === 'open' ? (
          <Button
            size="xs"
            variant="secondary"
            disabled={busy}
            onClick={resolve}
          >
            Mark resolved
          </Button>
        ) : discussion?.status === 'resolved' ? (
          <Badge tone="green">Resolved</Badge>
        ) : null}
      </div>

      {error && (
        <div className="mt-3">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {discussion?.subject && !compact && (
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
            Thread
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-900">
            {discussion.subject}
          </p>
          {discussion.signer_name && (
            <p className="mt-1 text-xs text-slate-500">
              Signing task: {discussion.signer_name}
            </p>
          )}
        </div>
      )}

      <div className="mt-4 max-h-80 space-y-2 overflow-auto">
        {(discussion?.comments || []).map((item) => {
          const ownComment = (
            user?.id
            && String(item.author_user_id) === String(user.id)
          );

          return (
            <div
              key={item.id}
              className="rounded-lg bg-slate-50 p-3"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <strong className="block truncate text-[11px] text-slate-700">
                    {item.author_name}
                  </strong>
                  <span className="text-[10px] text-slate-500">
                    {formatDay(item.created_at)}
                    {item.edited_at && !item.is_deleted
                      ? ' · edited'
                      : ''}
                  </span>
                </div>

                {ownComment && !item.is_deleted && (
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      type="button"
                      title="Edit comment"
                      aria-label="Edit comment"
                      disabled={busy}
                      onClick={() => beginEdit(item)}
                      className="rounded p-1 text-slate-500 hover:bg-white hover:text-slate-900 disabled:opacity-50"
                    >
                      <Pencil size={13} />
                    </button>

                    <button
                      type="button"
                      title="Delete comment"
                      aria-label="Delete comment"
                      disabled={busy}
                      onClick={() => remove(item)}
                      className="rounded p-1 text-slate-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                )}
              </div>

              {item.is_deleted ? (
                <p className="mt-2 text-xs italic text-slate-400">
                  This comment was deleted.
                </p>
              ) : (
                <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-700">
                  {item.body}
                </p>
              )}
            </div>
          );
        })}

        {!(discussion?.comments || []).length && (
          <p className="text-xs text-slate-500">
            No comments yet.
          </p>
        )}
      </div>

      {editingId && (
        <div className="mt-3 flex items-center justify-between rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-800">
          <span>Editing your comment</span>
          <button
            type="button"
            onClick={resetComposer}
            className="rounded p-1 hover:bg-blue-100"
            aria-label="Cancel editing"
          >
            <X size={13} />
          </button>
        </div>
      )}

      <div className="relative mt-3">
        <textarea
          aria-label="Discussion comment"
          rows={3}
          className="w-full rounded-lg border border-slate-300 p-3 text-xs"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          placeholder="Add a question or type @ to mention a colleague"
        />

        {mentionResults.length > 0 && (
          <div className="absolute inset-x-0 bottom-full z-20 mb-1 max-h-52 overflow-auto rounded-lg border border-slate-200 bg-white p-1 shadow-xl">
            {mentionResults.map((person) => (
              <button
                key={person.user_id}
                type="button"
                onClick={() => selectMention(person)}
                className="flex w-full items-start gap-2 rounded-md px-3 py-2 text-left hover:bg-slate-50"
              >
                <AtSign
                  size={14}
                  className="mt-0.5 shrink-0 text-blue-600"
                />
                <span className="min-w-0">
                  <strong className="block truncate text-xs text-slate-900">
                    {person.full_name}
                  </strong>
                  <span className="block truncate text-[10px] text-slate-500">
                    {person.job_title || 'Employee'}
                  </span>
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      <Button
        className="mt-2 w-full"
        size="sm"
        variant="secondary"
        disabled={busy || body.trim().length < 2}
        onClick={submit}
      >
        {editingId ? 'Save changes' : 'Reply'}
      </Button>
    </section>
  );
}
