import { Building2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';

import Navbar from '../components/navigation/Navbar.jsx';
import { getPageTitle } from '../config/navigation.js';
import Sidebar from '../components/navigation/Sidebar.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Skeleton from '../components/ui/Skeleton.jsx';
import useAuth from '../hooks/useAuth.js';
import usePermissions from '../hooks/usePermissions.js';
import useTenant from '../hooks/useTenant.js';

const TENANT_SCOPED_ROUTES = [
  '/dashboard',
  '/employees',
  '/org-chart',
  '/departments',
  '/documents',
  '/signature-requests',
  '/leave',
  '/attendance',
  '/tasks',
  '/onboarding',
  '/goals',
];

function isTenantScopedRoute(pathname) {
  return TENANT_SCOPED_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

function initialCollapsedState() {
  try {
    return window.localStorage.getItem('kinetic.sidebarCollapsed') === 'true';
  } catch {
    return false;
  }
}

export default function DashboardLayout() {
  const [sidebarOpenPath, setSidebarOpenPath] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(initialCollapsedState);
  const location = useLocation();
  const sidebarOpen = sidebarOpenPath === location.pathname;
  const { user } = useAuth();
  const { hasRole } = usePermissions();
  const { tenantId, loading: tenantLoading } = useTenant();

  useEffect(() => {
    document.title = `${getPageTitle(location.pathname)} | Kinetic`;
  }, [location.pathname]);

  useEffect(() => {
    try {
      window.localStorage.setItem('kinetic.sidebarCollapsed', String(sidebarCollapsed));
    } catch {
      // Storage is optional; the shell still works without persistence.
    }
  }, [sidebarCollapsed]);

  const needsTenant = hasRole('SUPER_ADMIN') && isTenantScopedRoute(location.pathname);

  let content;

  if (needsTenant && tenantLoading) {
    content = (
      <div className="space-y-5">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-48 w-full" />
        <div className="grid gap-4 md:grid-cols-3"><Skeleton className="h-32" /><Skeleton className="h-32" /><Skeleton className="h-32" /></div>
      </div>
    );
  } else if (needsTenant && !tenantId) {
    content = (
      <Card className="mx-auto max-w-2xl py-10 text-center">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-xl border border-blue-100 bg-blue-50 text-blue-700">
          <Building2 size={22} />
        </span>
        <h1 className="mt-4 text-xl font-bold text-slate-950">Select an organization</h1>
        <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-600">
          Platform administrators must choose an organization before opening tenant-scoped people, time, file, onboarding, or signature workflows.
        </p>
        <Link to="/organizations" className="mt-5 inline-flex">
          <Button variant="primary"><Building2 size={16} /> Choose organization</Button>
        </Link>
      </Card>
    );
  } else {
    content = (
      <div className="kinetic-page-enter" key={location.pathname}>
        <Outlet
          key={hasRole('SUPER_ADMIN') ? tenantId || 'platform' : user?.id || user?.email || 'tenant-user'}
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f4f6f8]">
      <a href="#main-content" className="kinetic-skip-link">Skip to main content</a>
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpenPath(null)}
        collapsed={sidebarCollapsed}
        onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
      />
      <div className={`min-h-screen transition-[padding] duration-200 ${sidebarCollapsed ? 'lg:pl-[76px]' : 'lg:pl-[236px]'}`}>
        <Navbar onMenu={() => setSidebarOpenPath(location.pathname)} />
        <main id="main-content" tabIndex={-1} className="mx-auto max-w-[1540px] p-4 md:p-5 lg:p-6">
          {content}
        </main>
      </div>
    </div>
  );
}
