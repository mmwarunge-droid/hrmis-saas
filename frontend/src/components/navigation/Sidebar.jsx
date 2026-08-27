import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { navigationGroups, visibleNavigation } from '../../config/navigation.js';
import useAuth from '../../hooks/useAuth.js';
import usePermissions from '../../hooks/usePermissions.js';
import useTenant from '../../hooks/useTenant.js';
import Avatar from '../ui/Avatar.jsx';
import Button from '../ui/Button.jsx';
import KineticLogo from '../ui/KineticLogo.jsx';

function SidebarContent({ collapsed, mobile, onClose, onToggleCollapsed }) {
  const { user } = useAuth();
  const { hasPermission, hasRole } = usePermissions();
  const {
    tenantId,
    tenants,
    loading: tenantLoading,
    error: tenantError,
    isSuperAdmin,
    setTenantId,
  } = useTenant();
  const groups = visibleNavigation(navigationGroups, {
    hasPermission,
    hasRole,
    hasEmployeeProfile: Boolean(user?.employee_profile),
  });
  const compact = collapsed && !mobile;

  return (
    <div className="flex h-full flex-col bg-white">
      <div className={`flex h-16 items-center border-b border-slate-200 ${compact ? 'justify-center px-2' : 'justify-between px-4'}`}>
        <KineticLogo compact={compact} />
        {mobile && (
          <Button variant="ghost" size="sm" className="px-2" onClick={onClose} aria-label="Close navigation">
            <X size={18} />
          </Button>
        )}
      </div>

      {isSuperAdmin && !compact && (
        <div className="border-b border-slate-200 p-3">
          <label htmlFor={mobile ? 'active-organization-mobile' : 'active-organization'} className="block text-[10px] font-bold uppercase tracking-[0.13em] text-slate-600">
            Active organization
          </label>
          <select
            id={mobile ? 'active-organization-mobile' : 'active-organization'}
            value={tenantId || ''}
            disabled={tenantLoading}
            onChange={(event) => setTenantId(event.target.value)}
            className="mt-1.5 min-h-9 w-full rounded-lg border border-slate-300 bg-white px-2.5 text-xs font-medium text-slate-800 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
          >
            <option value="">{tenantLoading ? 'Loading organizations…' : 'Select organization'}</option>
            {tenants.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name}</option>)}
          </select>
          {tenantError && <p className="mt-1.5 text-[11px] leading-4 text-red-600">{tenantError}</p>}
        </div>
      )}

      <nav className={`flex-1 overflow-y-auto py-4 ${compact ? 'px-2' : 'px-3'}`} aria-label="Primary navigation">
        <div className="space-y-5">
          {groups.map((group) => (
            <div key={group.label}>
              {!compact && <p className="mb-1.5 px-2 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-600">{group.label}</p>}
              <div className="space-y-0.5">
                {group.links.map(({ to, label, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    onClick={onClose}
                    title={compact ? label : undefined}
                    className={({ isActive }) => `relative flex min-h-10 items-center rounded-lg text-sm font-semibold transition ${
                      compact ? 'justify-center px-2' : 'gap-3 px-2.5'
                    } ${
                      isActive
                        ? 'bg-blue-50 text-blue-800 before:absolute before:bottom-2 before:left-0 before:top-2 before:w-0.5 before:rounded-full before:bg-blue-700'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                    }`}
                  >
                    <Icon size={18} strokeWidth={1.9} className="shrink-0" />
                    {!compact && <span className="truncate">{label}</span>}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </div>
      </nav>

      <div className="border-t border-slate-200 p-3">
        <div className={`flex items-center ${compact ? 'justify-center' : 'gap-3 rounded-lg px-1 py-1'}`} title={compact ? user?.full_name : undefined}>
          <Avatar name={user?.full_name} size="sm" />
          {!compact && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-bold text-slate-900">{user?.full_name}</p>
              <p className="truncate text-[10px] capitalize text-slate-500">{user?.roles?.[0]?.replaceAll('_', ' ').toLowerCase()}</p>
            </div>
          )}
        </div>
        {!mobile && (
          <button
            type="button"
            onClick={onToggleCollapsed}
            className={`mt-2 flex h-8 w-full items-center rounded-lg text-xs font-semibold text-slate-500 hover:bg-slate-100 hover:text-slate-900 ${compact ? 'justify-center' : 'gap-2 px-2'}`}
            aria-label={compact ? 'Expand navigation' : 'Collapse navigation'}
          >
            {compact ? <ChevronRight size={16} /> : <><ChevronLeft size={16} /><span>Collapse</span></>}
          </button>
        )}
      </div>
    </div>
  );
}

export default function Sidebar({ open = false, onClose, collapsed = false, onToggleCollapsed }) {
  return (
    <>
      <aside className={`fixed inset-y-0 left-0 z-40 hidden border-r border-slate-200 bg-white transition-[width] duration-200 lg:block ${collapsed ? 'w-[76px]' : 'w-[236px]'}`}>
        <SidebarContent collapsed={collapsed} onToggleCollapsed={onToggleCollapsed} />
      </aside>
      {open && (
        <div className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-[2px] lg:hidden" onMouseDown={onClose}>
          <aside className="kinetic-drawer-enter h-full w-[286px] max-w-[88vw] border-r border-slate-200 bg-white shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
            <SidebarContent mobile onClose={onClose} />
          </aside>
        </div>
      )}
    </>
  );
}
