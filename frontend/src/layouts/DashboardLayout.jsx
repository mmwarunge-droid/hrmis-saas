import { Outlet } from 'react-router-dom';
import Navbar from '../components/navigation/Navbar.jsx';
import Sidebar from '../components/navigation/Sidebar.jsx';

export default function DashboardLayout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar />
      <div className="lg:pl-72">
        <Navbar />
        <main className="p-4 md:p-8"><Outlet /></main>
      </div>
    </div>
  );
}
