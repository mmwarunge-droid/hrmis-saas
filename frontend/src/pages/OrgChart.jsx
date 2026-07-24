import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Network, Search, UsersRound } from 'lucide-react';
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

function PersonCard({ employee, collapsed, onToggle }) {
  const hasReports = employee.children.length > 0;

  return (
    <div className="relative z-10 inline-block min-w-64 rounded-3xl border border-slate-200 bg-white p-4 text-left shadow-sm">
      <div className="flex items-start gap-3">
        <Avatar name={employee.full_name} />
        <div className="min-w-0 flex-1">
          <Link to={`/employees/${employee.id}`} className="block truncate font-bold text-slate-950 hover:text-cyan-700">
            {employee.full_name}
          </Link>
          <p className="truncate text-xs font-medium text-cyan-700">
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
  const [meta, setMeta] = useState({ total: 0, root_count: 0, manager_count: 0, max_depth: 0 });
  const [query, setQuery] = useState('');
  const [collapsedIds, setCollapsedIds] = useState(() => new Set());
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    employeeApi.orgChart()
      .then((response) => {
        if (cancelled) return;
        setRoots(response.data.roots || []);
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

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="People structure"
        title="Organization chart"
        description="Explore reporting lines, team composition and role visibility across the organization."
      />

      {error && <Alert type="error">{error}</Alert>}

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="relative w-full max-w-xl">
            <Search className="pointer-events-none absolute left-3 top-3 text-slate-400" size={18} />
            <Input
              className="pl-10"
              placeholder="Search people, roles or departments"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
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
        <Card className="overflow-x-auto bg-gradient-to-b from-slate-50 to-white">
          <div className="org-tree py-6">
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
        </Card>
      )}

      <div className="flex items-center gap-2 text-xs text-slate-500">
        <Network size={15} />
        Reporting lines are generated from each employee’s “Reports to” assignment.
      </div>
    </div>
  );
}
