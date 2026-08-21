import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Maximize2,
  Minus,
  Network,
  Plus,
  RotateCcw,
  Search,
  UsersRound,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { employeeApi } from '../api/employeeApi';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import Input from '../components/ui/Input.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 1.5;
const ZOOM_STEP = 0.1;

function clampZoom(value) {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(value.toFixed(2))));
}

function PersonCard({ employee, collapsed, onToggle }) {
  const hasReports = employee.children.length > 0;

  return (
    <div className="relative z-10 inline-block min-w-64 rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm">
      <div className="flex items-start gap-3">
        <Avatar
          name={employee.full_name}
          src={employee.profile_photo_url}
          alt={employee.full_name}
        />
        <div className="min-w-0 flex-1">
          <Link to={`/employees/${employee.id}`} className="block truncate font-bold text-slate-950 hover:text-blue-700">
            {employee.full_name}
          </Link>
          <p className="truncate text-xs font-medium text-blue-700">
            {employee.job_title || 'Role not assigned'}
          </p>
        </div>

        {hasReports && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="shrink-0 px-2"
            onClick={onToggle}
            aria-label={`${collapsed ? 'Expand' : 'Collapse'} ${employee.full_name}`}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
          </Button>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-1">
        <Badge>{employee.department_name || 'No department'}</Badge>
        {employee.work_location && <Badge tone="blue">{employee.work_location}</Badge>}
        {hasReports && (
          <Badge tone="violet">
            {employee.direct_report_count} direct {employee.direct_report_count === 1 ? 'report' : 'reports'}
          </Badge>
        )}
      </div>
    </div>
  );
}

function TreeNode({ employee, collapsedIds, forceExpanded, toggle }) {
  const collapsed = !forceExpanded && collapsedIds.has(employee.id);
  const visibleChildren = collapsed ? [] : employee.children;

  return (
    <li>
      <PersonCard
        employee={employee}
        collapsed={collapsed}
        onToggle={() => toggle(employee.id)}
      />

      {visibleChildren.length > 0 && (
        <ul>
          {visibleChildren.map((report) => (
            <TreeNode
              key={report.id}
              employee={report}
              collapsedIds={collapsedIds}
              forceExpanded={forceExpanded}
              toggle={toggle}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function filterTree(nodes, query) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return nodes;

  return nodes.flatMap((node) => {
    const children = filterTree(node.children, query);
    const haystack = [
      node.full_name,
      node.job_title,
      node.department_name,
      node.work_location,
    ].filter(Boolean).join(' ').toLowerCase();

    if (haystack.includes(normalized) || children.length > 0) {
      return [{ ...node, children }];
    }
    return [];
  });
}

export default function OrgChart() {
  const [roots, setRoots] = useState([]);
  const [vacancies, setVacancies] = useState([]);
  const [meta, setMeta] = useState({ total: 0, root_count: 0, manager_count: 0, max_depth: 0 });
  const [query, setQuery] = useState('');
  const [collapsedIds, setCollapsedIds] = useState(() => new Set());
  const [zoom, setZoom] = useState(1);
  const [error, setError] = useState('');
  const viewportRef = useRef(null);
  const treeRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    employeeApi.orgChart()
      .then((response) => {
        if (cancelled) return;
        setRoots(response.data.roots || []);
        setVacancies(response.data.vacancies || []);
        setMeta(response.data.meta || { total: 0, root_count: 0, manager_count: 0, max_depth: 0 });
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.error?.message || 'Unable to load organization chart');
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const visibleRoots = useMemo(() => filterTree(roots, query), [roots, query]);
  const forceExpanded = query.trim().length > 0;

  const toggle = (employeeId) => {
    setCollapsedIds((current) => {
      const next = new Set(current);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });
  };

  const adjustZoom = (delta) => {
    setZoom((current) => clampZoom(current + delta));
  };

  const resetZoom = () => {
    setZoom(1);
    const viewport = viewportRef.current;
    if (!viewport) return;

    if (typeof viewport.scrollTo === 'function') {
      viewport.scrollTo({ left: 0, top: 0, behavior: 'smooth' });
      return;
    }

    viewport.scrollLeft = 0;
    viewport.scrollTop = 0;
  };

  const fitChart = () => {
    const viewport = viewportRef.current;
    const tree = treeRef.current;
    if (!viewport || !tree) return;

    const availableWidth = Math.max(1, viewport.clientWidth - 48);
    const naturalWidth = Math.max(1, tree.scrollWidth);
    setZoom(clampZoom(Math.min(1, availableWidth / naturalWidth)));

    if (typeof viewport.scrollTo === 'function') {
      viewport.scrollTo({ left: 0, top: 0, behavior: 'smooth' });
    } else {
      viewport.scrollLeft = 0;
      viewport.scrollTop = 0;
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="People structure"
        title="Organization chart"
        description="Explore reporting lines, team composition and role visibility across the organization."
      />

      {error && <Alert type="error">{error}</Alert>}

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="relative w-full max-w-xl">
            <Search className="pointer-events-none absolute left-3 top-3 text-slate-500" size={18} />
            <Input
              className="pl-10"
              placeholder="Search people, roles or departments"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
            <span className="flex items-center gap-1"><UsersRound size={15} /> {meta.total} people</span>
            <span>{meta.manager_count} managers</span>
            <span>{meta.max_depth} levels</span>
          </div>
        </div>
      </Card>

      {visibleRoots.length === 0 ? (
        <EmptyState
          title="No organization structure found"
          description={query
            ? 'No reporting line matches this search.'
            : 'Assign a manager on each employee profile to build the hierarchy.'}
        />
      ) : (
        <Card className="relative overflow-hidden bg-gradient-to-b from-slate-50 to-white p-0">
          <div
            ref={viewportRef}
            className="max-h-[72vh] min-h-[520px] overflow-auto px-5 py-6 md:px-6"
            aria-label="Organization chart canvas"
          >
            <div
              ref={treeRef}
              className="org-tree origin-top transition-transform duration-200 ease-out motion-reduce:transition-none"
              style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}
            >
              <ul>
                {visibleRoots.map((root) => (
                  <TreeNode
                    key={root.id}
                    employee={root}
                    collapsedIds={collapsedIds}
                    forceExpanded={forceExpanded}
                    toggle={toggle}
                  />
                ))}
              </ul>
            </div>
          </div>

          <div className="absolute bottom-4 right-4 z-20 rounded-xl border border-slate-200 bg-white/95 p-1.5 shadow-xl backdrop-blur">
            <div className="flex items-center gap-1" role="group" aria-label="Organization chart zoom controls">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-9 w-9 px-0"
                onClick={() => adjustZoom(-ZOOM_STEP)}
                disabled={zoom <= MIN_ZOOM}
                aria-label="Zoom out organization chart"
              >
                <Minus size={17} />
              </Button>
              <span className="min-w-14 text-center text-sm font-bold tabular-nums text-slate-700" aria-live="polite">
                {Math.round(zoom * 100)}%
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-9 w-9 px-0"
                onClick={() => adjustZoom(ZOOM_STEP)}
                disabled={zoom >= MAX_ZOOM}
                aria-label="Zoom in organization chart"
              >
                <Plus size={17} />
              </Button>
              <span className="mx-1 h-6 w-px bg-slate-200" aria-hidden="true" />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-9 w-9 px-0"
                onClick={fitChart}
                aria-label="Fit organization chart to view"
                title="Fit to view"
              >
                <Maximize2 size={17} />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-9 w-9 px-0"
                onClick={resetZoom}
                aria-label="Reset organization chart zoom"
                title="Reset zoom"
              >
                <RotateCcw size={17} />
              </Button>
            </div>
          </div>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-600">
        <span className="flex items-center gap-2">
          <Network size={15} />
          Reporting lines are generated from each employee’s “Reports to” assignment.
        </span>
        <span>Zoom controls affect only the chart canvas, not the rest of Kinetic.</span>
      </div>

      {vacancies.length > 0 && (
        <Card>
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-full bg-slate-100 text-slate-500"><UsersRound size={18} /></span>
            <div>
              <h2 className="font-bold text-slate-950">Vacant positions</h2>
              <p className="text-sm text-slate-500">Positions whose previous employee is no longer active are kept visible without showing that former employee in the active org structure.</p>
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {vacancies.map((vacancy) => (
              <div key={vacancy.id} className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4">
                <Avatar name="Vacant position" />
                <p className="mt-3 font-semibold text-slate-800">{vacancy.job_title || 'Vacant position'}</p>
                <p className="text-xs text-slate-500">{vacancy.department_name || 'Department not assigned'} · Vacant</p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
