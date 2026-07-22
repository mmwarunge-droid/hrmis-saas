import { Outlet } from 'react-router-dom';

export default function AuthLayout() {
  return <main className="min-h-screen bg-slate-950 grid place-items-center px-4"><Outlet /></main>;
}
