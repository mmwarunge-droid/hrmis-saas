import {
  Bell,
  CheckCheck,
  CircleAlert,
  FileText,
  UserPlus,
  Target,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { notificationApi } from '../../api/notificationApi.js';
import Button from '../ui/Button.jsx';

const iconByType = {
  leave_approval: CircleAlert,
  leave_decision: CheckCheck,
  onboarding: UserPlus,
  signature: FileText,
  signature_discussion: FileText,
  compliance: FileText,
  goal: Target,
};

function relativeTime(value) {
  if (!value) return '';
  const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  const ranges = [
    ['year', 31536000],
    ['month', 2592000],
    ['week', 604800],
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ];
  for (const [unit, size] of ranges) {
    if (Math.abs(seconds) >= size) {
      return formatter.format(Math.round(seconds / size), unit);
    }
  }
  return 'just now';
}

export default function NotificationMenu() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const menuRef = useRef(null);
  const navigate = useNavigate();

  const load = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      const response = await notificationApi.list({ per_page: 12 });
      setItems(response.data.items || []);
      setUnreadCount(response.data.unread_count || 0);
      setError('');
    } catch (err) {
      if (!quiet) {
        setError(err.error?.message || 'Unable to load notifications.');
      }
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load({ quiet: true });
    const interval = window.setInterval(
      () => load({ quiet: true }),
      60000,
    );
    return () => window.clearInterval(interval);
  }, [load]);

  useEffect(() => {
    if (open) load();
  }, [load, open]);

  useEffect(() => {
    const close = (event) => {
      if (!menuRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const openNotification = async (notification) => {
    if (!notification.read_at) {
      try {
        await notificationApi.read(notification.id);
        setUnreadCount((count) => Math.max(0, count - 1));
        setItems((current) => current.map((item) => (
          item.id === notification.id
            ? { ...item, read_at: new Date().toISOString() }
            : item
        )));
      } catch {
        // Navigation remains available if read-state persistence fails.
      }
    }
    setOpen(false);
    if (notification.action_url) navigate(notification.action_url);
  };

  const readAll = async () => {
    await notificationApi.readAll();
    const timestamp = new Date().toISOString();
    setItems((current) => current.map((item) => ({
      ...item,
      read_at: item.read_at || timestamp,
    })));
    setUnreadCount(0);
  };

  return (
    <div ref={menuRef} className="relative">
      <Button
        variant="ghost"
        size="sm"
        className="relative px-2"
        aria-label={unreadCount
          ? `Notifications, ${unreadCount} unread`
          : 'Notifications'}
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((value) => !value)}
      >
        <Bell size={18} />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-1 min-w-5 rounded-full bg-blue-700 px-1.5 py-0.5 text-center text-[10px] font-bold leading-4 text-white ring-2 ring-white">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </Button>

      {open && (
        <div
          role="menu"
          aria-label="Notifications"
          className="absolute right-0 top-11 w-[min(92vw,390px)] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
        >
          <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
            <div>
              <p className="text-sm font-bold text-slate-900">Notifications</p>
              <p className="mt-0.5 text-xs text-slate-500">
                {unreadCount
                  ? `${unreadCount} update${unreadCount === 1 ? '' : 's'} need attention.`
                  : 'You are all caught up.'}
              </p>
            </div>
            {unreadCount > 0 && (
              <button
                type="button"
                className="text-xs font-semibold text-blue-700 hover:text-blue-900"
                onClick={readAll}
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-[420px] overflow-y-auto">
            {loading && (
              <p className="px-4 py-8 text-center text-sm text-slate-500">
                Loading notifications…
              </p>
            )}
            {!loading && error && (
              <div className="px-4 py-6 text-center">
                <p className="text-sm font-semibold text-red-700">{error}</p>
                <button
                  type="button"
                  className="mt-2 text-xs font-semibold text-blue-700"
                  onClick={() => load()}
                >
                  Try again
                </button>
              </div>
            )}
            {!loading && !error && items.length === 0 && (
              <div className="px-4 py-9 text-center">
                <Bell className="mx-auto text-slate-300" size={24} />
                <p className="mt-2 text-sm font-semibold text-slate-700">
                  No notifications
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Workflow updates will appear here.
                </p>
              </div>
            )}
            {!loading && !error && items.map((item) => {
              const Icon = iconByType[item.notification_type] || Bell;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="menuitem"
                  onClick={() => openNotification(item)}
                  className={`flex w-full items-start gap-3 border-b border-slate-100 px-4 py-3 text-left last:border-b-0 hover:bg-slate-50 ${item.read_at ? 'bg-white' : 'bg-blue-50/55'}`}
                >
                  <span className={`mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg ${item.read_at ? 'bg-slate-100 text-slate-600' : 'bg-blue-100 text-blue-700'}`}>
                    <Icon size={17} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-start gap-2">
                      <span className="flex-1 text-sm font-semibold text-slate-900">
                        {item.title}
                      </span>
                      {!item.read_at && (
                        <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-blue-700" />
                      )}
                    </span>
                    {item.body && (
                      <span className="mt-1 block text-xs leading-5 text-slate-600">
                        {item.body}
                      </span>
                    )}
                    <span className="mt-1.5 block text-[11px] text-slate-400">
                      {relativeTime(item.created_at)}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
