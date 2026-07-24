import { Bell, HelpCircle, LogOut, Menu, Search } from 'lucide-react';
import useAuth from '../../hooks/useAuth.js';
import Avatar from '../ui/Avatar.jsx';
import Button from '../ui/Button.jsx';

export default function Navbar({ onMenu }) {
  const { user, logout } = useAuth();
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-slate-50/85 px-4 py-3 backdrop-blur-xl md:px-8">
      <div className="flex items-center gap-3">
        <Button variant="secondary" size="sm" className="lg:hidden" onClick={onMenu}><Menu size={18} /></Button>
        <div className="relative hidden max-w-xl flex-1 md:block">
          <Search className="pointer-events-none absolute left-4 top-3 text-slate-400" size={17} />
          <input aria-label="Global search" className="w-full rounded-2xl border border-slate-200 bg-white py-2.5 pl-11 pr-4 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100" placeholder="Search people, documents or actions" />
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" size="sm" aria-label="Help"><HelpCircle size={18} /></Button>
          <Button variant="ghost" size="sm" aria-label="Notifications" className="relative"><Bell size={18} /><span className="absolute right-2 top-1.5 h-2 w-2 rounded-full bg-rose-500 ring-2 ring-slate-50" /></Button>
          <div className="hidden items-center gap-3 border-l border-slate-200 pl-3 sm:flex">
            <Avatar name={user?.full_name} size="sm" />
            <div className="hidden lg:block"><p className="max-w-36 truncate text-sm font-semibold text-slate-900">{user?.full_name}</p><p className="text-[11px] text-slate-500">{user?.roles?.[0]?.replaceAll('_', ' ')}</p></div>
          </div>
          <Button variant="ghost" size="sm" onClick={logout} aria-label="Logout"><LogOut size={18} /></Button>
        </div>
      </div>
    </header>
  );
}
