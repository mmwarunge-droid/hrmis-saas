import {
  Bot,
  ChevronDown,
  HelpCircle,
  LogOut,
  Menu,
  Search,
  Settings,
  UserRound,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { getPageTitle } from '../../config/navigation.js';
import useAuth from '../../hooks/useAuth.js';
import Avatar from '../ui/Avatar.jsx';
import Button from '../ui/Button.jsx';
import NotificationMenu from '../notifications/NotificationMenu.jsx';
import GlobalSearch from './GlobalSearch.jsx';

export default function Navbar({ onMenu }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [searchOpen, setSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const menuRef = useRef(null);
  const title = getPageTitle(location.pathname);

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
      }
    };
    document.addEventListener('mousedown', closeMenus);
    return () => document.removeEventListener('mousedown', closeMenus);
  }, []);

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
            <span className="truncate">Quick navigation</span>
            <span className="ml-auto hidden items-center gap-1 rounded border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-slate-500 xl:flex">⌘ K</span>
          </button>

          <div ref={menuRef} className="relative ml-auto flex items-center gap-1.5">
            <Button variant="ghost" size="sm" className="px-2 md:hidden" onClick={() => setSearchOpen(true)} aria-label="Search">
              <Search size={18} />
            </Button>
            <Link to="/ask-kinetic" className="hidden sm:block">
              <Button variant="soft" size="sm"><Bot size={16} /> <span className="hidden xl:inline">Ask Kinetic</span></Button>
            </Link>
            <Link to="/help" className="hidden md:block">
              <Button variant="ghost" size="sm" className="px-2" aria-label="Help center">
                <HelpCircle size={18} />
              </Button>
            </Link>
            <NotificationMenu />
            <div className="relative ml-1 border-l border-slate-200 pl-2">
              <button
                type="button"
                onClick={() => setProfileOpen((value) => !value)}
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
