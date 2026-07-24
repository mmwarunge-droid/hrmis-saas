import { useEffect, useMemo, useState } from 'react';
import { Network, Search, UsersRound } from 'lucide-react';
import { employeeApi } from '../api/employeeApi';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import Input from '../components/ui/Input.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';

function PersonCard({ employee, department }) {
  return (
    <div className="min-w-56 rounded-3xl border border-slate-200 bg-white p-4 text-left shadow-sm">
      <div className="flex items-center gap-3">
        <Avatar name={employee.full_name} />
        <div className="min-w-0"><p className="truncate font-bold text-slate-950">{employee.full_name}</p><p className="truncate text-xs font-medium text-cyan-700">{employee.job_title || 'Role not assigned'}</p></div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1"><Badge>{department || 'No department'}</Badge>{employee.work_location && <Badge tone="blue">{employee.work_location}</Badge>}</div>
    </div>
  );
}

export default function OrgChart() {
  const [employees, setEmployees] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([employeeApi.list(), employeeApi.departments()])
      .then(([people, teams]) => { setEmployees(people.data.items || []); setDepartments(teams.data.items || []); })
      .catch((err) => setError(err.error?.message || 'Unable to load organization chart'));
  }, []);

  const departmentNames = useMemo(() => Object.fromEntries(departments.map((item) => [item.id, item.name])), [departments]);
  const visible = useMemo(() => employees.filter((employee) => !query || `${employee.full_name} ${employee.job_title || ''} ${departmentNames[employee.department_id] || ''}`.toLowerCase().includes(query.toLowerCase())), [employees, query, departmentNames]);
  const ids = useMemo(() => new Set(visible.map((item) => item.id)), [visible]);
  const roots = visible.filter((employee) => !employee.manager_id || !ids.has(employee.manager_id));
  const childrenFor = (id) => visible.filter((employee) => employee.manager_id === id);

  return (
    <div className="space-y-7">
      <PageHeader eyebrow="People structure" title="Organization chart" description="Explore reporting lines, team composition and role visibility across the organization." />
      {error && <Alert type="error">{error}</Alert>}
      <Card>
        <div className="relative max-w-xl"><Search className="pointer-events-none absolute left-3 top-3 text-slate-400" size={18} /><Input className="pl-10" placeholder="Search the org chart" value={query} onChange={(event) => setQuery(event.target.value)} /></div>
      </Card>
      {visible.length === 0 ? <EmptyState title="No organization structure yet" description="Assign managers and departments to employee profiles to build the chart." /> : (
        <Card className="overflow-x-auto bg-gradient-to-b from-slate-50 to-white">
          <div className="min-w-[760px] space-y-12 py-4">
            {roots.map((root) => {
              const directReports = childrenFor(root.id);
              return (
                <div key={root.id} className="text-center">
                  <div className="inline-block"><PersonCard employee={root} department={departmentNames[root.department_id]} /></div>
                  {directReports.length > 0 && (
                    <>
                      <div className="mx-auto h-8 w-px bg-slate-300" />
                      <div className="mx-auto h-px max-w-4xl bg-slate-300" />
                      <div className="mt-7 flex flex-wrap justify-center gap-6">
                        {directReports.map((report) => {
                          const team = childrenFor(report.id);
                          return (
                            <div key={report.id} className="relative">
                              <div className="absolute -top-7 left-1/2 h-7 w-px bg-slate-300" />
                              <PersonCard employee={report} department={departmentNames[report.department_id]} />
                              {team.length > 0 && <div className="mt-3 rounded-2xl bg-slate-100 p-3 text-left"><p className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500"><UsersRound size={14} /> {team.length} direct reports</p>{team.slice(0, 4).map((person) => <div key={person.id} className="flex items-center gap-2 py-1 text-xs text-slate-700"><Avatar name={person.full_name} size="sm" className="h-6 w-6 rounded-lg text-[9px]" /> {person.full_name}</div>)}</div>}
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      )}
      <div className="flex items-center gap-2 text-xs text-slate-500"><Network size={15} /> Reporting lines are generated from each employee’s manager assignment.</div>
    </div>
  );
}
