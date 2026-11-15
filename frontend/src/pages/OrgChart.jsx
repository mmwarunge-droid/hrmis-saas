import { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { employeeApi } from '../api/employeeApi';
import { TenantContext } from '../context/TenantContext.jsx';
import { AuthContext } from '../context/AuthContext.jsx';
import Button from '../components/ui/Button.jsx';
import Alert from '../components/ui/Alert.jsx';
import Modal from '../components/ui/Modal.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import { initials } from '../components/ui/Avatar.jsx';
import {
  ancestors,
  CARD_HEIGHT,
  CARD_WIDTH,
  categoryColor,
  indexPeople,
  layoutHierarchy,
} from '../components/orgChart/hierarchy';

const EMPTY_FILTERS = {
  department_name: '',
  work_location: '',
  employment_status: '',
  manager_id: '',
  job_title: '',
};
const LABELS = {
  department_name: 'Department',
  work_location: 'Work location',
  employment_status: 'Employment status',
  manager_id: 'Reporting manager',
  job_title: 'Job title',
};
const MIN_ZOOM = 0.1,
  MAX_ZOOM = 2;
const clamp = (n) =>
  Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round(n * 100) / 100));

function Photo({ person }) {
  const [failed, setFailed] = useState(false);
  return person.profile_photo_url && !failed ? (
    <img
      loading="lazy"
      src={person.profile_photo_url}
      onError={() => setFailed(true)}
      alt={person.full_name}
      className="h-10 w-10 shrink-0 rounded-full object-cover"
    />
  ) : (
    <span
      className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-blue-100 text-blue-800"
      aria-hidden="true"
    >
      {initials(person.full_name)}
    </span>
  );
}

export default function OrgChart() {
  const auth = useContext(AuthContext);
  const tenant = useContext(TenantContext);
  const [params] = useSearchParams();
  const contextKey = `${auth?.user?.id || ''}:${tenant?.tenantId || auth?.user?.tenant_id || ''}`;
  const [loadedContext, setLoadedContext] = useState(null);
  const [data, setData] = useState(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState('');
  const [revision, setRevision] = useState(0),
    [selected, setSelected] = useState(null);
  const [collapsed, setCollapsed] = useState(new Set()),
    [query, setQuery] = useState(''),
    [search, setSearch] = useState('');
  const [filters, setFilters] = useState(EMPTY_FILTERS),
    [mode, setMode] = useState('tree'),
    [colorBy, setColorBy] = useState('');
  const [zoom, setZoom] = useState(1),
    [viewport, setViewport] = useState({
      x: 0,
      y: 0,
      width: 1200,
      height: 600,
    });
  const [focusId, setFocusId] = useState(null),
    [editing, setEditing] = useState(false),
    [manager, setManager] = useState('');
  const [reportLimit, setReportLimit] = useState(50);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [saving, setSaving] = useState(false),
    [editError, setEditError] = useState('');
  const viewportRef = useRef(null),
    treeRef = useRef(null),
    drag = useRef(null),
    panelRef = useRef(null);
  const canEdit =
    auth?.user?.roles?.includes('SUPER_ADMIN') ||
    auth?.user?.permissions?.includes('employee:update') ||
    false;
  const canRead =
    auth?.user?.roles?.includes('SUPER_ADMIN') ||
    auth?.user?.permissions?.includes('employee:read') ||
    false;
  useEffect(() => {
    let active = true;
    const changingTenant = loadedContext !== contextKey;
    setLoading(true);
    setError('');
    setEditing(false);
    if (changingTenant) {
      setData(null);
      setSelected(null);
      setFilters(EMPTY_FILTERS);
      setQuery('');
    }
    employeeApi
      .orgChart({ format: 'flat' })
      .then((response) => {
        if (!active) return;
        setData(response.data);
        setLoadedContext(contextKey);
        const index = indexPeople(response.data);
        if (changingTenant)
          setCollapsed(
            new Set(
              [...index.people.values()]
                .filter((p) => p.manager_id && p.children.length)
                .map((p) => p.id),
            ),
          );
        setFocusId(
          index.people.has(selected)
            ? selected
            : params.get('employee') || index.roots[0] || null,
        );
      })
      .catch((err) => {
        if (active)
          setError(err.error?.message || 'Unable to load organization chart');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // URL employee focus is handled separately; fetching is tied to tenant and refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contextKey, revision]);
  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim().toLowerCase()), 180);
    return () => clearTimeout(timer);
  }, [query]);
  const index = useMemo(
    () => indexPeople(loadedContext === contextKey ? data || {} : {}),
    [data, loadedContext, contextKey],
  );
  const layout = useMemo(
    () => layoutHierarchy(index, collapsed, filters, mode),
    [index, collapsed, filters, mode],
  );
  const person = index.people.get(selected);
  useEffect(() => setReportLimit(50), [selected]);
  const searchResults = useMemo(
    () =>
      search
        ? [...index.people.values()].filter((p) =>
            [
              p.full_name,
              p.employee_number,
              p.job_title,
              p.department_name,
              p.work_location,
            ].some((v) => v?.toLowerCase().includes(search)),
          )
        : [],
    [index, search],
  );
  const categories = useMemo(
    () =>
      colorBy
        ? [
            ...new Set(
              [...index.people.values()].map(
                (p) => p[colorBy] || 'Not specified',
              ),
            ),
          ].sort()
        : [],
    [index, colorBy],
  );
  const filterOptions = useMemo(
    () =>
      Object.fromEntries(
        Object.keys(EMPTY_FILTERS).map((key) => [
          key,
          [
            ...new Set(
              [...index.people.values()].map((p) => p[key]).filter(Boolean),
            ),
          ].sort(),
        ]),
      ),
    [index],
  );
  const managerOptions = useMemo(() => {
    if (!editing || !person) return [];
    const excluded = new Set([person.id]);
    const pending = [...person.children];
    while (pending.length) {
      const id = pending.pop();
      if (excluded.has(id)) continue;
      excluded.add(id);
      pending.push(...(index.people.get(id)?.children || []));
    }
    return [...index.people.values()].filter((p) => !excluded.has(p.id));
  }, [editing, person, index]);
  const measure = () => {
    const el = viewportRef.current;
    if (el)
      setViewport({
        x: el.scrollLeft,
        y: el.scrollTop,
        width: el.clientWidth,
        height: el.clientHeight,
      });
  };
  const panelOpen = Boolean(person);
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return undefined;
    measure();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [loading, panelOpen]);
  const reveal = (id) => {
    if (!index.people.has(id)) return;
    if (!layout.positions.has(id)) setFilters(EMPTY_FILTERS);
    setCollapsed((old) => {
      const next = new Set(old);
      ancestors(id, index.people).forEach((key) => next.delete(key));
      return next;
    });
    setSelected(id);
    setFocusId(id);
  };
  useEffect(() => {
    const id = params.get('employee');
    if (id && index.people.has(id)) {
      setCollapsed((old) => {
        const next = new Set(old);
        ancestors(id, index.people).forEach((key) => next.delete(key));
        return next;
      });
      setSelected(id);
      setFocusId(id);
    }
  }, [index, params]);
  useEffect(() => {
    if (!focusId || !layout.positions.has(focusId)) return;
    const p = layout.positions.get(focusId),
      el = viewportRef.current;
    if (el) {
      el.scrollLeft = Math.max(
        0,
        (p.x + CARD_WIDTH / 2) * zoom - el.clientWidth / 2,
      );
      el.scrollTop = Math.max(
        0,
        (p.y + CARD_HEIGHT / 2) * zoom - el.clientHeight / 2,
      );
      measure();
    }
    setFocusId(null);
  }, [focusId, layout, zoom]);
  const toggle = (id) =>
    setCollapsed((old) => {
      const next = new Set(old);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const closePanel = () => {
    const id = selected;
    setSelected(null);
    requestAnimationFrame(() =>
      document.getElementById(`org-person-${id}`)?.focus(),
    );
  };
  const center = () => {
    const el = viewportRef.current;
    if (el) {
      el.scrollLeft = Math.max(0, (layout.width * zoom - el.clientWidth) / 2);
      el.scrollTop = 0;
      measure();
    }
  };
  const fit = () => {
    const el = viewportRef.current;
    if (!el) return;
    setZoom(
      clamp(
        Math.min(
          (el.clientWidth - 32) / layout.width,
          (el.clientHeight - 32) / layout.height,
          1,
        ),
      ),
    );
    el.scrollLeft = 0;
    el.scrollTop = 0;
    measure();
  };
  const reset = () => {
    setSettingsOpen(false);
    setFocusId(index.roots[0] || null);
    setFilters(EMPTY_FILTERS);
    setQuery('');
    setMode('tree');
    setColorBy('');
    setZoom(1);
    setSelected(null);
    setCollapsed(
      new Set(
        [...index.people.values()]
          .filter((p) => p.manager_id && p.children.length)
          .map((p) => p.id),
      ),
    );
    if (viewportRef.current) {
      viewportRef.current.scrollLeft = 0;
      viewportRef.current.scrollTop = 0;
    }
  };
  const visible = [...layout.positions.values()].filter(
    (p) =>
      p.id === selected ||
      ((p.x + CARD_WIDTH) * zoom >= viewport.x - 300 &&
        p.x * zoom <= viewport.x + viewport.width + 300 &&
        (p.y + CARD_HEIGHT) * zoom >= viewport.y - 300 &&
        p.y * zoom <= viewport.y + viewport.height + 300),
  );
  const saveManager = async () => {
    if (!person || loadedContext !== contextKey) return;
    setSaving(true);
    setEditError('');
    try {
      await employeeApi.update(person.id, { manager_id: manager || null });
      setEditing(false);
      setRevision((n) => n + 1);
    } catch (err) {
      setEditError(err.error?.message || 'Unable to change reporting manager');
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="space-y-4">
      <PageHeader
        title="Organization chart"
        description="Explore your organization’s reporting relationships."
      />
      <nav aria-label="People views" className="flex gap-4">
        <Link to="/employees" className="text-blue-700 underline">
          People Directory
        </Link>
        <span aria-current="page">Org Chart</span>
      </nav>
      {error && (
        <Alert type="error">
          {error}{' '}
          <Button onClick={() => setRevision((n) => n + 1)}>Retry</Button>
        </Alert>
      )}
      {loading && <p role="status">Loading organization chart…</p>}
      {!loading && data && loadedContext === contextKey && (
        <>
          {params.get('employee') &&
            !index.people.has(params.get('employee')) && (
              <Alert>
                This employee is not in the active chart or is unavailable to
                your account.
              </Alert>
            )}
          {!!data.integrity_issues?.length && (
            <Alert type="warning">
              {data.integrity_issues.length} reporting relationships need
              review. Unavailable managers or cyclic links are shown as separate
              roots; stored assignments have not changed.
              <details>
                <summary>Review relationship issues</summary>
                <ul>
                  {data.integrity_issues.map((issue, i) => (
                    <li key={i}>
                      {index.people.get(issue.employee_id)?.full_name ||
                        'Employee'}
                      : {issue.code.replaceAll('_', ' ')}
                    </li>
                  ))}
                </ul>
              </details>
            </Alert>
          )}
          <div className="rounded-xl border bg-white p-4 space-y-3">
            <label className="block text-sm font-medium">
              Search people, roles or departments
              <input
                className="mt-1 block w-full rounded-lg border p-2"
                placeholder="Search people, roles or departments"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
            {search && (
              <div
                aria-label="Employee search results"
                className="max-h-48 overflow-auto"
              >
                <p role="status" className="text-sm text-slate-600">
                  {searchResults.length} matches
                  {searchResults.length > 50
                    ? '; showing the first 50. Refine your search.'
                    : ''}
                </p>
                {searchResults.slice(0, 50).map((p) => (
                  <button
                    key={p.id}
                    className="block w-full rounded p-2 text-left hover:bg-blue-50"
                    onClick={() => {
                      setFilters(EMPTY_FILTERS);
                      reveal(p.id);
                    }}
                  >
                    {p.full_name} · {p.job_title || 'Role not assigned'}
                  </button>
                ))}
                {!searchResults.length && (
                  <p>No visible employee matches this search.</p>
                )}
              </div>
            )}
            <details
              open={settingsOpen}
              onToggle={(event) => setSettingsOpen(event.currentTarget.open)}
            >
              <summary className="cursor-pointer font-medium">
                View settings and filters
              </summary>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <label>
                  Layout
                  <select
                    aria-label="Layout"
                    className="block w-full rounded border p-2"
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                  >
                    <option value="tree">Tree</option>
                    <option value="stacked">Stacked</option>
                  </select>
                </label>
                <label>
                  Color cards by
                  <select
                    aria-label="Color cards by"
                    className="block w-full rounded border p-2"
                    value={colorBy}
                    onChange={(e) => setColorBy(e.target.value)}
                  >
                    <option value="">Neutral</option>
                    {[
                      'department_name',
                      'work_location',
                      'employment_status',
                    ].map((k) => (
                      <option key={k} value={k}>
                        {LABELS[k]}
                      </option>
                    ))}
                  </select>
                </label>
                {Object.keys(EMPTY_FILTERS).map((key) => (
                  <label key={key}>
                    {LABELS[key]}
                    <select
                      aria-label={`Filter ${LABELS[key]}`}
                      className="block w-full rounded border p-2"
                      value={filters[key]}
                      onChange={(e) =>
                        setFilters({ ...filters, [key]: e.target.value })
                      }
                    >
                      <option value="">All</option>
                      {filterOptions[key].map((value) => (
                        <option key={value} value={value}>
                          {key === 'manager_id'
                            ? index.people.get(value)?.full_name ||
                              'Unavailable manager'
                            : value}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <p className="mt-2 text-sm text-slate-600">
                Relationship: reporting manager. Filters include matching
                employees and their ancestors. Active and probation employees
                only.
              </p>
            </details>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => setFilters(EMPTY_FILTERS)}>
                Reset filters
              </Button>
              <Button onClick={reset}>Restore default view</Button>
              <Button onClick={() => setRevision((n) => n + 1)}>
                Refresh chart
              </Button>
            </div>
            <p role="status">
              {layout.matching.size} matching employees ·{' '}
              {data.meta?.total || index.people.size} people ·{' '}
              {data.meta?.manager_count || 0} managers
            </p>
            {categories.length > 0 && (
              <ul
                aria-label="Color legend"
                className="flex max-h-24 flex-wrap gap-3 overflow-auto text-xs"
              >
                {categories.map((value) => (
                  <li key={value}>
                    <span
                      aria-hidden="true"
                      style={{ backgroundColor: categoryColor(value) }}
                      className="mr-1 inline-block h-3 w-3 rounded"
                    />
                    {value}
                  </li>
                ))}
              </ul>
            )}
          </div>
          {!index.people.size ? (
            <p>
              No organization structure found. Add active employee records to
              get started.
            </p>
          ) : (
            <div
              className={`grid min-w-0 gap-4 ${person ? 'xl:grid-cols-[minmax(0,1fr)_320px]' : 'grid-cols-1'}`}
            >
              <section className="min-w-0 overflow-hidden rounded-xl border bg-slate-50">
                <div
                  role="group"
                  aria-label="Organization chart zoom controls"
                  className="flex flex-wrap items-center gap-2 border-b bg-white p-3"
                >
                  <Button
                    aria-label="Zoom out organization chart"
                    disabled={zoom <= MIN_ZOOM}
                    onClick={() => setZoom((z) => clamp(z - 0.1))}
                  >
                    −
                  </Button>
                  <span aria-live="polite">{Math.round(zoom * 100)}%</span>
                  <Button
                    aria-label="Zoom in organization chart"
                    disabled={zoom >= MAX_ZOOM}
                    onClick={() => setZoom((z) => clamp(z + 0.1))}
                  >
                    +
                  </Button>
                  <Button
                    aria-label="Reset organization chart zoom"
                    onClick={() => setZoom(1)}
                  >
                    Reset zoom
                  </Button>
                  <Button
                    aria-label="Fit organization chart to view"
                    onClick={fit}
                  >
                    Fit
                  </Button>
                  <Button onClick={center}>Center</Button>
                  <Button disabled={!selected} onClick={() => reveal(selected)}>
                    Focus selected
                  </Button>
                </div>
                <div
                  ref={viewportRef}
                  role="region"
                  tabIndex={0}
                  aria-label="Organization chart canvas"
                  className="h-[60vh] min-h-80 overflow-auto overscroll-contain"
                  onScroll={measure}
                  onPointerDown={(e) => {
                    if (
                      e.pointerType !== 'mouse' ||
                      e.button !== 0 ||
                      e.target.closest('button,a,input,select')
                    )
                      return;
                    drag.current = {
                      x: e.clientX,
                      y: e.clientY,
                      left: e.currentTarget.scrollLeft,
                      top: e.currentTarget.scrollTop,
                    };
                    e.currentTarget.setPointerCapture?.(e.pointerId);
                  }}
                  onPointerMove={(e) => {
                    if (drag.current) {
                      e.currentTarget.scrollLeft =
                        drag.current.left + drag.current.x - e.clientX;
                      e.currentTarget.scrollTop =
                        drag.current.top + drag.current.y - e.clientY;
                    }
                  }}
                  onPointerUp={() => {
                    drag.current = null;
                  }}
                  onPointerCancel={() => {
                    drag.current = null;
                  }}
                  onKeyDown={(e) => {
                    if (e.target !== e.currentTarget) return;
                    const moves = {
                      ArrowLeft: [-80, 0],
                      ArrowRight: [80, 0],
                      ArrowUp: [0, -80],
                      ArrowDown: [0, 80],
                    };
                    if (moves[e.key]) {
                      e.preventDefault();
                      e.currentTarget.scrollLeft += moves[e.key][0];
                      e.currentTarget.scrollTop += moves[e.key][1];
                      measure();
                    }
                  }}
                >
                  <div
                    style={{
                      width: layout.width * zoom,
                      height: layout.height * zoom,
                      position: 'relative',
                    }}
                  >
                    <div
                      ref={treeRef}
                      className="org-chart-surface"
                      style={{
                        width: layout.width,
                        height: layout.height,
                        transform: `scale(${zoom})`,
                        transformOrigin: 'top left',
                        position: 'absolute',
                      }}
                    >
                      <svg
                        aria-hidden="true"
                        width={layout.width}
                        height={layout.height}
                        className="pointer-events-none absolute inset-0"
                      >
                        {visible
                          .filter(
                            (p) => p.parent && layout.positions.has(p.parent),
                          )
                          .map((p) => {
                            const parent = layout.positions.get(p.parent);
                            return (
                              <path
                                key={p.id}
                                d={
                                  mode === 'tree'
                                    ? `M ${parent.x + CARD_WIDTH / 2} ${parent.y + CARD_HEIGHT} V ${p.y - 32} H ${p.x + CARD_WIDTH / 2} V ${p.y}`
                                    : `M ${parent.x + 20} ${parent.y + CARD_HEIGHT} V ${p.y + 60} H ${p.x}`
                                }
                                fill="none"
                                stroke="#94a3b8"
                                strokeWidth="2"
                              />
                            );
                          })}
                      </svg>
                      {visible.map((position) => {
                        const p = index.people.get(position.id);
                        return (
                          <article
                            key={p.id}
                            aria-label={`${p.full_name} employee card`}
                            className={`absolute rounded-xl border bg-white p-3 shadow-sm ${selected === p.id ? 'ring-2 ring-blue-600' : ''} ${layout.matching.has(p.id) ? '' : 'opacity-60'}`}
                            style={{
                              left: position.x,
                              top: position.y,
                              width: CARD_WIDTH,
                              height: CARD_HEIGHT,
                              borderTop: `4px solid ${colorBy ? categoryColor(p[colorBy] || 'Not specified') : '#cbd5e1'}`,
                            }}
                          >
                            <button
                              id={`org-person-${p.id}`}
                              className="flex w-full gap-2 text-left focus-visible:outline-blue-600"
                              aria-label={`View ${p.full_name}`}
                              aria-pressed={selected === p.id}
                              onClick={() => {
                                setSelected(p.id);
                                requestAnimationFrame(() =>
                                  panelRef.current?.focus(),
                                );
                              }}
                            >
                              <Photo person={p} />
                              <span className="min-w-0">
                                <span
                                  className="block truncate font-semibold"
                                  title={p.full_name}
                                >
                                  {p.full_name}
                                </span>
                                <span
                                  className="block truncate text-xs text-blue-700"
                                  title={p.job_title}
                                >
                                  {p.job_title || 'Role not assigned'}
                                </span>
                              </span>
                            </button>
                            <p
                              className="mt-2 truncate text-xs"
                              title={p.department_name}
                            >
                              {p.department_name || 'No department'}
                            </p>
                            <p className="truncate text-xs text-slate-600">
                              {p.work_location || 'Location not specified'} ·{' '}
                              {p.employment_status || ''}
                            </p>
                            <div className="mt-2 flex items-center justify-between gap-1 text-xs">
                              <span>
                                {p.direct_report_count || 0} direct ·{' '}
                                {p.indirect_report_count || 0} indirect
                              </span>
                              {p.children.length > 0 && (
                                <button
                                  className="rounded border px-2 py-1"
                                  aria-expanded={
                                    !collapsed.has(p.id) ||
                                    Object.values(filters).some(Boolean)
                                  }
                                  aria-label={`${collapsed.has(p.id) ? 'Expand' : 'Collapse'} ${p.full_name}`}
                                  onClick={() => toggle(p.id)}
                                  disabled={Object.values(filters).some(
                                    Boolean,
                                  )}
                                >
                                  {collapsed.has(p.id) ? '+' : '−'}
                                </button>
                              )}
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  </div>
                </div>
                <p className="p-3 text-xs text-slate-600">
                  Drag blank space or scroll to pan. Touch: swipe. Keyboard:
                  focus the canvas and use arrow keys; use search to reach any
                  employee. Counts include all visible-to-you reports, including
                  collapsed branches.
                </p>
              </section>
              {person && (
                <aside
                  ref={panelRef}
                  tabIndex={-1}
                  aria-label="Employee details"
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') closePanel();
                  }}
                  className="min-w-0 space-y-3 rounded-xl border bg-white p-4 xl:max-h-[75vh] xl:overflow-auto"
                >
                  <Button onClick={closePanel}>Close employee details</Button>
                  <Photo key={person.id} person={person} />
                  <h2 className="text-lg font-bold">{person.full_name}</h2>
                  <dl className="space-y-2 text-sm">
                    {[
                      ['Job title', person.job_title],
                      ['Department', person.department_name],
                      ['Work location', person.work_location],
                      ['Email', person.email],
                      ['Start date', person.hire_date],
                      [
                        'Tenure',
                        person.hire_date
                          ? `${Math.max(0, Math.floor((Date.now() - new Date(person.hire_date).getTime()) / 86400000))} days`
                          : null,
                      ],
                      ['Employment status', person.employment_status],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <dt className="text-slate-500">{label}</dt>
                        <dd className="break-words">
                          {value || 'Not provided'}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  {canRead && (
                    <Link
                      className="block text-blue-700 underline"
                      to={`/employees/${person.id}`}
                    >
                      View employee profile
                    </Link>
                  )}
                  <h3 className="font-semibold">Reporting manager</h3>
                  {index.people.has(person.manager_id) ? (
                    <button
                      className="text-blue-700 underline"
                      onClick={() => reveal(person.manager_id)}
                    >
                      {index.people.get(person.manager_id).full_name}
                    </button>
                  ) : (
                    <p>No visible reporting manager</p>
                  )}
                  <details>
                    <summary>Show reporting hierarchy</summary>
                    {ancestors(person.id, index.people)
                      .reverse()
                      .map((id) => (
                        <button
                          key={id}
                          className="block text-blue-700 underline"
                          onClick={() => reveal(id)}
                        >
                          {index.people.get(id).full_name}
                        </button>
                      ))}
                  </details>
                  <h3 className="font-semibold">
                    Direct reports ({person.children.length})
                  </h3>
                  {person.children.length ? (
                    <ul>
                      {person.children.slice(0, reportLimit).map((id) => (
                        <li key={id}>
                          <button
                            className="text-blue-700 underline"
                            onClick={() => reveal(id)}
                          >
                            {index.people.get(id).full_name}
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>No direct reports</p>
                  )}
                  {person.children.length > reportLimit && (
                    <Button
                      onClick={() => setReportLimit((limit) => limit + 50)}
                    >
                      Show more direct reports
                    </Button>
                  )}
                  {canEdit && (
                    <Button
                      onClick={() => {
                        setManager(person.manager_id || '');
                        setEditError('');
                        setEditing(true);
                      }}
                    >
                      Change reporting manager
                    </Button>
                  )}
                </aside>
              )}
            </div>
          )}
        </>
      )}
      <Modal
        open={editing && !!person}
        title="Confirm reporting manager change"
        onClose={() => {
          if (!saving) setEditing(false);
        }}
        footer={
          <Button disabled={saving} onClick={saveManager}>
            {saving ? 'Saving…' : 'Confirm change'}
          </Button>
        }
      >
        <p>
          This updates {person?.full_name}’s reporting assignment through the
          existing employee workflow, effective today, and records job history.
        </p>
        {editError && <Alert type="error">{editError}</Alert>}
        <label className="block mt-3">
          New reporting manager
          <select
            aria-label="New reporting manager"
            className="block w-full rounded border p-2"
            value={manager}
            onChange={(e) => setManager(e.target.value)}
          >
            <option value="">No manager</option>
            {managerOptions.map((p) => (
              <option key={p.id} value={p.id}>
                {p.full_name}
              </option>
            ))}
          </select>
        </label>
      </Modal>
    </div>
  );
}
