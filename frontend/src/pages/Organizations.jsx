import {
  useCallback,
  useEffect,
  useState,
} from 'react';
import {
  ArrowRight,
  Building2,
  Globe2,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  UsersRound,
  X,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { tenantApi } from '../api/tenantApi';
import OrganizationEditForm from '../components/organizations/OrganizationEditForm.jsx';
import OrganizationProvisionForm from '../components/organizations/OrganizationProvisionForm.jsx';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import Input from '../components/ui/Input.jsx';
import Modal from '../components/ui/Modal.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import Pagination from '../components/ui/Pagination.jsx';
import Select from '../components/ui/Select.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import useTenant from '../hooks/useTenant.js';

const STATUS_TONES = {
  active: 'green',
  suspended: 'amber',
  archived: 'slate',
};

export default function Organizations() {
  const navigate = useNavigate();
  const {
    tenantId,
    setTenantId,
    reloadTenants,
  } = useTenant();
  const [tenants, setTenants] = useState([]);
  const [summary, setSummary] = useState({
    total: 0,
    active: 0,
    suspended: 0,
    archived: 0,
    users: 0,
    admins: 0,
  });
  const [meta, setMeta] = useState({
    page: 1,
    per_page: 12,
    total: 0,
    pages: 1,
  });
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [sort, setSort] = useState('name:asc');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadOrganizations = useCallback(async () => {
    setLoading(true);
    setError('');
    const [sortKey, direction] = sort.split(':');
    try {
      const response = await tenantApi.list({
        page,
        per_page: 12,
        q: query || undefined,
        status: status || undefined,
        sort: sortKey,
        direction,
      });
      setTenants(response.data.items || []);
      setMeta(response.data.meta || {
        page,
        per_page: 12,
        total: 0,
        pages: 1,
      });
    } catch (err) {
      setError(err.error?.message || 'Unable to load organizations');
    } finally {
      setLoading(false);
    }
  }, [page, query, sort, status]);

  const loadSummary = useCallback(async () => {
    try {
      const response = await tenantApi.summary();
      setSummary(response.data);
    } catch (err) {
      setError(err.error?.message || 'Unable to load platform totals');
    }
  }, []);

  useEffect(() => {
    loadOrganizations();
  }, [loadOrganizations]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const refresh = async () => {
    await Promise.all([
      loadOrganizations(),
      loadSummary(),
      reloadTenants(),
    ]);
  };

  const provision = async (payload) => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const response = await tenantApi.provision(payload);
      setOpen(false);
      setSuccess(
        response.data.invitation?.delivery === 'sent'
          ? `${response.data.organization.name} is ready. A secure activation invitation was sent to ${response.data.admin.email}.`
          : `${response.data.organization.name} is ready, but the administrator invitation could not be delivered. Use Share Invite Link from Access & users.`,
      );
      await refresh();
    } catch (err) {
      setError(err.error?.message || 'Organization provisioning failed');
    } finally {
      setSaving(false);
    }
  };

  const updateOrganization = async (payload) => {
    if (!selectedTenant) return;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const response = await tenantApi.update(
        selectedTenant.id,
        payload,
      );
      setSelectedTenant(null);
      const revoked = response.data.revoked_sessions || 0;
      setSuccess(
        revoked
          ? `${response.data.name} updated and ${revoked} active session${revoked === 1 ? '' : 's'} revoked.`
          : `${response.data.name} updated.`,
      );
      await refresh();
    } catch (err) {
      setError(err.error?.message || 'Organization update failed');
    } finally {
      setSaving(false);
    }
  };

  const resetFilters = () => {
    setQuery('');
    setStatus('');
    setSort('name:asc');
    setPage(1);
  };
  const hasFilters = Boolean(query || status || sort !== 'name:asc');

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform administration"
        title="Organizations"
        description="Provision isolated client workspaces, review complete platform adoption and control workspace lifecycle without relying on first-page records."
        actions={(
          <Button variant="accent" onClick={() => setOpen(true)}>
            <Plus size={17} /> New organization
          </Button>
        )}
      />

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Organizations" value={summary.total} detail="Complete platform workspace count" icon={Building2} tone="blue" />
        <StatCard label="Active workspaces" value={summary.active} detail={`${summary.suspended} suspended · ${summary.archived} archived`} icon={Globe2} tone="emerald" />
        <StatCard label="Tenant users" value={summary.users} detail="Accounts across every workspace" icon={UsersRound} tone="blue" />
        <StatCard label="Organization admins" value={summary.admins} detail="CLIENT ADMIN assignments" icon={ShieldCheck} tone="violet" />
      </div>

      <Card className="p-0">
        <div className="grid gap-3 p-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
          <Input
            aria-label="Search organizations"
            icon={Search}
            placeholder="Search name, slug, country, industry or region"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
          <Select
            aria-label="Filter organizations by status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
            <option value="archived">Archived</option>
          </Select>
          <Select
            aria-label="Sort organizations"
            value={sort}
            onChange={(event) => {
              setSort(event.target.value);
              setPage(1);
            }}
          >
            <option value="name:asc">Name A–Z</option>
            <option value="name:desc">Name Z–A</option>
            <option value="people:desc">Most users</option>
            <option value="admins:desc">Most admins</option>
            <option value="created_at:desc">Newest workspace</option>
            <option value="status:asc">Status</option>
          </Select>
          {hasFilters && (
            <Button variant="ghost" onClick={resetFilters}>
              <X size={15} /> Clear
            </Button>
          )}
        </div>
        <div className="border-t border-slate-200 px-4 py-2.5 text-xs text-slate-500">
          Showing {tenants.length} of {meta.total} matching organizations
        </div>
      </Card>

      {!loading && tenants.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No organizations match these filters' : 'No organizations yet'}
          description={hasFilters
            ? 'Clear the filters or adjust the search terms.'
            : 'Create the first client workspace and its administrator in one secure flow.'}
          action={!hasFilters && (
            <Button variant="accent" onClick={() => setOpen(true)}>
              <Plus size={16} /> Provision workspace
            </Button>
          )}
        />
      ) : (
        <>
          <div className="grid gap-5 xl:grid-cols-2">
            {(loading ? Array.from({ length: 4 }) : tenants).map((tenant, index) => (
              loading ? (
                <div
                  key={`loading-${index}`}
                  className="h-80 animate-pulse rounded-xl bg-slate-200"
                />
              ) : (
                <Card key={tenant.id} className="overflow-hidden">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex min-w-0 items-center gap-4">
                      <Avatar name={tenant.name} size="lg" className="rounded-xl" />
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="truncate text-lg font-bold text-slate-950">{tenant.name}</h2>
                          <Badge tone={STATUS_TONES[tenant.status] || 'slate'}>{tenant.status}</Badge>
                        </div>
                        <p className="mt-1 truncate text-sm text-slate-500">
                          {tenant.industry || 'Industry not specified'} · {tenant.country || 'Global'}
                        </p>
                      </div>
                    </div>
                    <Badge tone="blue">{tenant.billing_plan || 'mvp'}</Badge>
                  </div>

                  <div className="mt-6 grid grid-cols-3 gap-3">
                    <div className="rounded-lg bg-slate-50 p-3">
                      <p className="text-xs text-slate-500">People</p>
                      <p className="mt-1 text-xl font-bold">{tenant.user_count}</p>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-3">
                      <p className="text-xs text-slate-500">Admins</p>
                      <p className="mt-1 text-xl font-bold">{tenant.admin_count}</p>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-3">
                      <p className="text-xs text-slate-500">Region</p>
                      <p className="mt-1 truncate text-sm font-bold">{tenant.compliance_region || 'Default'}</p>
                    </div>
                  </div>

                  <div className="mt-5 border-t border-slate-100 pt-4">
                    <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Workspace administrator</p>
                    {tenant.primary_admin ? (
                      <div className="mt-3 flex items-center gap-3">
                        <Avatar name={tenant.primary_admin.full_name} size="sm" />
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-slate-900">{tenant.primary_admin.full_name}</p>
                          <div className="mt-1 flex flex-wrap items-center gap-2">
                            <p className="truncate text-xs text-slate-500">{tenant.primary_admin.email}</p>
                            {tenant.primary_admin.account_status === 'invited' && (
                              <Badge tone="amber">Invited</Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <p className="mt-2 text-sm text-amber-700">No CLIENT ADMIN assigned.</p>
                    )}
                  </div>

                  <div className="mt-5 flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
                    <Button
                      variant="secondary"
                      onClick={() => setSelectedTenant(tenant)}
                      aria-label={`Manage ${tenant.name}`}
                    >
                      <Pencil size={16} /> Manage
                    </Button>
                    <Button
                      variant={String(tenantId) === String(tenant.id) ? 'primary' : 'secondary'}
                      disabled={tenant.status !== 'active'}
                      onClick={() => {
                        setTenantId(tenant.id);
                        navigate('/dashboard');
                      }}
                    >
                      {tenant.status !== 'active'
                        ? 'Workspace unavailable'
                        : String(tenantId) === String(tenant.id)
                          ? 'Current workspace'
                          : 'Open workspace'}
                      <ArrowRight size={16} />
                    </Button>
                  </div>
                </Card>
              )
            ))}
          </div>

          {!loading && meta.total > 0 && (
            <Pagination
              page={meta.page}
              pageSize={meta.per_page}
              total={meta.total}
              onPageChange={setPage}
              label="organizations"
            />
          )}
        </>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Provision organization"
        size="xl"
      >
        <OrganizationProvisionForm onSubmit={provision} loading={saving} />
      </Modal>

      <Modal
        open={Boolean(selectedTenant)}
        onClose={() => setSelectedTenant(null)}
        title="Manage organization"
        description="Update workspace details and lifecycle status."
        size="lg"
      >
        {selectedTenant && (
          <OrganizationEditForm
            key={selectedTenant.id}
            organization={selectedTenant}
            loading={saving}
            onSubmit={updateOrganization}
          />
        )}
      </Modal>
    </div>
  );
}
