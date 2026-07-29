import { Building2 } from 'lucide-react';
import { useState } from 'react';
import {
  Link,
  Outlet,
  useLocation,
} from 'react-router-dom';

import Navbar from '../components/navigation/Navbar.jsx';
import Sidebar from '../components/navigation/Sidebar.jsx';
import Button from '../components/ui/Button.jsx';
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
];

function isTenantScopedRoute(pathname) {
  return TENANT_SCOPED_ROUTES.some(
    (route) => (
      pathname === route
      || pathname.startsWith(`${route}/`)
    ),
  );
}

export default function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const { hasRole } = usePermissions();
  const {
    tenantId,
    loading: tenantLoading,
  } = useTenant();

  const needsTenant = (
    hasRole('SUPER_ADMIN')
    && isTenantScopedRoute(location.pathname)
  );

  let content;

  if (needsTenant && tenantLoading) {
    content = (
      <div className="h-72 animate-pulse rounded-[2rem] bg-slate-100" />
    );
  } else if (needsTenant && !tenantId) {
    content = (
      <section className="mx-auto max-w-2xl rounded-[2rem] border border-slate-200 bg-white p-8 text-center shadow-sm">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-cyan-50 text-cyan-700">
          <Building2 size={24} />
        </span>
        <h1 className="mt-5 text-2xl font-bold text-slate-950">
          Select an organization
        </h1>
        <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-600">
          Platform administrators must choose an organization before
          opening tenant-scoped people, leave, document, onboarding or
          signature workflows.
        </p>
        <Link to="/organizations" className="mt-6 inline-flex">
          <Button variant="accent">
            <Building2 size={17} />
            Choose organization
          </Button>
        </Link>
      </section>
    );
  } else {
    content = (
      <Outlet
        key={
          hasRole('SUPER_ADMIN')
            ? tenantId || 'platform'
            : 'tenant-user'
        }
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="lg:pl-72">
        <Navbar onMenu={() => setSidebarOpen(true)} />
        <main className="mx-auto max-w-[1600px] p-4 md:p-8">
          {content}
        </main>
      </div>
    </div>
  );
}
