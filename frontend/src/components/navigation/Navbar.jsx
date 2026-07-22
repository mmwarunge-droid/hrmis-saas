import Button from '../ui/Button.jsx';
import useAuth from '../../hooks/useAuth';

export default function Navbar() {
  const { user, logout } = useAuth();
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur md:px-8">
      <div><p className="text-sm text-slate-500">Welcome back</p><h2 className="font-semibold text-slate-900">{user?.full_name}</h2></div>
      <div className="flex items-center gap-3"><span className="hidden rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 md:inline">{user?.roles?.join(', ')}</span><Button variant="secondary" onClick={logout}>Logout</Button></div>
    </header>
  );
}
