import {
  Bell,
  Bot,
  CalendarDays,
  ChevronDown,
  HelpCircle,
  LogOut,
  Menu,
  Search,
  Settings,
  UserRound,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { leaveApi } from '../../api/leaveApi.js';
import { getPageTitle } from '../../config/navigation.js';
import useAuth from '../../hooks/useAuth.js';
import Avatar from '../ui/Avatar.jsx';
import Button from '../ui/Button.jsx';
import GlobalSearch from './GlobalSearch.jsx';

function formatLeavePeriod(item) {
  const formatter = new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short' });
  const start = item.start_date ? formatter.format(new Date(`${item.start_date}T00:00:00`)) : 'No start date';
  const end = item.end_date ? formatter.format(new Date(`${item.end_date}T00:00:00`)) : 'No end date';
  return `${start} – ${end}`;
}

function notificationQuery(user) {
  const roles = new Set(user?.roles || []);
  const canSeeOrganizationQueue = ['SUPER_ADMIN', 'CLIENT_ADMIN', 'HR_CONSULTANT']
    .some((role) => roles.has(role));
  return canSeeOrganizationQueue
    ? { status: 'pending', page: 1, per_page: 5 }
    : { view: 'approvals', page: 1, per_page: 5 };
}

export default function Navbar({ onMenu }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [searchOpen, setSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [leaveNotifications, setLeaveNotifications] = useState([]);
  const [notificationCount, setNotificationCount] = useState(0);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const menuRef = useRef(null);
  const title = getPageTitle(location.pathname);

  const loadLeaveNotifications = useCallback(async () => {
    if (!user) return;
    setNotificationsLoading(true);
    try {
      const response = await leaveApi.requests(notificationQuery(user));
      setLeaveNotifications(response.data.items || []);
      setNotificationCount(response.data.meta?.total || 0);
    } catch {
      // Keep the last known queue visible during transient API failures.
    } finally {
      setNotificationsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setSearchOpen(true);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    const closeMenus = (event) => {
      if (!menuRef.current?.contains(event.target)) {
        setProfileOpen(false);
        setNotificationsOpen(false);
      }
    };
    document.addEventListener('mousedown', closeMenus);
    return () => document.removeEventListener('mousedown', closeMenus);
  }, []);

  useEffect(() => {
    if (!user) return undefined;
    loadLeaveNotifications();
    const intervalId = window.setInterval(loadLeaveNotifications, 30000);
    window.addEventListener('focus', loadLeaveNotifications);
    window.addEventListener('kinetic:leave-queue-changed', loadLeaveNotifications);
    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener('focus', loadLeaveNotifications);
      window.removeEventListener('kinetic:leave-queue-changed', loadLeaveNotifications);
    };
  }, [loadLeaveNotifications, user]);

  const visibleNotificationCount = notificationCount > 99 ? '99+' : String(notificationCount);

  return (
    <>
      <header className="sticky top-0 z-30 h-16 border-b border-slate-200 bg-white/95 px-3 backdrop-blur md:px-5">
        <div className="mx-auto flex h-full max-w-[1540px] items-center gap-3">
          <Button variant="ghost" size="sm" className="px-2 lg:hidden" onClick={onMenu} aria-label="Open navigation">
            <Menu size={19} />
          </Button>
          <div className="min-w-0 lg:hidden">
            <p className="truncate text-sm font-bold text-slate-900">{title}</p>
          </div>

          <button
            type="button"
            onClick={() => setSearchOpen(true)}
            className="hidden h-10 min-w-0 max-w-[520px] flex-1 items-center gap-3 rounded-lg border border-slate-300 bg-slate-50 px-3 text-left text-sm text-slate-500 shadow-sm transition hover:border-slate-400 hover:bg-white md:flex"
          >
            <Search size={17} className="shrink-0" />
            <span className="truncate">Search Kinetic</span>
            <span className="ml-auto hidden items-center gap-1 rounded border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-slate-500 xl:flex">⌘ K</span>
          </button>

          <div ref={menuRef} className="relative ml-auto flex items-center gap-1.5">
            <Button variant="ghost" size="sm" className="px-2 md:hidden" onClick={() => setSearchOpen(true)} aria-label="Search">
              <Search size={18} />
            </Button>
            <Link to="/ask-kinetic" className="hidden sm:block">
              <Button variant="soft" size="sm"><Bot size={16} /> <span className="hidden xl:inline">Ask Kinetic</span></Button>
            </Link>
            <Button variant="ghost" size="sm" className="hidden px-2 md:inline-flex" aria-label="Help">
              <HelpCircle size={18} />
            </Button>
            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                className="relative px-2"
                aria-label={`Notifications, ${notificationCount} pending time-off request${notificationCount === 1 ? '' : 's'}`}
                aria-expanded={notificationsOpen}
                onClick={() => {
                  setNotificationsOpen((value) => !value);
                  setProfileOpen(false);
                  loadLeaveNotifications();
                }}
              >
                <Bell size={18} />
                {notificationCount > 0 && (
                  <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-red-600 px-1 text-[9px] font-extrabold leading-none text-white ring-2 ring-white">
                    {visibleNotificationCount}
                  </span>
                )}
              </Button>
              {notificationsOpen && (
                <div className="absolute right-0 top-11 w-80 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                  <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
                    <div>
                      <p className="text-sm font-bold text-slate-900">Time-off notifications</p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {notificationCount
                          ? `${notificationCount} request${notificationCount === 1 ? '' : 's'} awaiting attention.`
                          : 'No requests are waiting for attention.'}
                      </p>
                    </div>
                    {notificationCount > 0 && (
                      <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-bold text-red-700">
                        {visibleNotificationCount}
                      </span>
                    )}
                  </div>
                  {notificationsLoading && leaveNotifications.length === 0 ? (
                    <div className="px-4 py-8 text-center text-sm text-slate-500">Loading notifications…</div>
                  ) : leaveNotifications.length > 0 ? (
                    <div className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
                      {leaveNotifications.map((item) => (
                        <Link
                          key={item.id}
                          to="/leave"
                          onClick={() => setNotificationsOpen(false)}
                          className="flex gap-3 px-4 py-3 transition hover:bg-slate-50"
                        >
                          <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-amber-50 text-amber-700">
                            <CalendarDays size={16} />
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate text-sm font-semibold text-slate-900">
                              {item.employee_name || 'Employee'} requested time off
                            </span>
                            <span className="mt-0.5 block text-xs text-slate-500">
                              {item.leave_type_name || 'Leave'} · {formatLeavePeriod(item)}
                            </span>
                          </span>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <div className="px-4 py-8 text-center">
                      <Bell className="mx-auto text-slate-300" size={23} />
                      <p className="mt-2 text-sm font-semibold text-slate-700">You’re all caught up</p>
                      <p className="mt-1 text-xs text-slate-500">No pending time-off requests.</p>
                    </div>
                  )}
                  <Link
                    to="/leave"
                    onClick={() => setNotificationsOpen(false)}
                    className="block border-t border-slate-100 px-4 py-3 text-center text-xs font-bold text-blue-700 hover:bg-blue-50"
                  >
                    Open time-off workspace
                  </Link>
                </div>
              )}
            </div>
            <div className="relative ml-1 border-l border-slate-200 pl-2">
              <button
                type="button"
                onClick={() => {
                  setProfileOpen((value) => !value);
                  setNotificationsOpen(false);
                }}
                className="flex items-center gap-2 rounded-lg p-1 pr-1.5 text-left hover:bg-slate-100"
                aria-expanded={profileOpen}
              >
                <Avatar name={user?.full_name} size="sm" />
                <span className="hidden min-w-0 lg:block">
                  <span className="block max-w-32 truncate text-xs font-bold text-slate-900">{user?.full_name}</span>
                  <span className="block max-w-32 truncate text-[10px] capitalize text-slate-500">{user?.roles?.[0]?.replaceAll('_', ' ').toLowerCase()}</span>
                </span>
                <ChevronDown size={14} className="hidden text-slate-400 lg:block" />
              </button>
              {profileOpen && (
                <div className="absolute right-0 top-12 w-60 overflow-hidden rounded-xl border border-slate-200 bg-white p-1.5 shadow-sm">
                  <div className="border-b border-slate-100 px-2.5 py-2.5">
                    <p className="truncate text-sm font-bold text-slate-900">{user?.full_name}</p>
                    <p className="truncate text-xs text-slate-500">{user?.email}</p>
                  </div>
                  <Link to="/profile" onClick={() => setProfileOpen(false)} className="mt-1 flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">
                    <UserRound size={16} /> My info
                  </Link>
                  <Link to="/settings" onClick={() => setProfileOpen(false)} className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">
                    <Settings size={16} /> Settings
                  </Link>
                  <button type="button" onClick={logout} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm font-medium text-red-700 hover:bg-red-50">
                    <LogOut size={16} /> Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>
      <GlobalSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
    </>
  );
}
