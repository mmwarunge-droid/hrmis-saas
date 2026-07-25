import { useEffect, useMemo, useState } from 'react';
import { CalendarClock, History, KeyRound, Pencil, UserRoundCheck } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { employeeApi } from '../api/employeeApi';
import EmployeeAccessForm from '../components/employees/EmployeeAccessForm.jsx';
import EmployeeForm from '../components/employees/EmployeeForm.jsx';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Modal from '../components/ui/Modal.jsx';
import Spinner from '../components/ui/Spinner.jsx';
import usePermissions from '../hooks/usePermissions.js';

export default function EmployeeDetails() {
  const { id } = useParams();
  const [employee, setEmployee] = useState(null);
  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [history, setHistory] = useState([]);
  const [open, setOpen] = useState(false);
  const [accessOpen, setAccessOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [accessSaving, setAccessSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const { hasPermission } = usePermissions();

  const load = async () => {
    const responses = await Promise.all([
      employeeApi.get(id),
      employeeApi.options(),
      employeeApi.departments(),
      employeeApi.history(id),
    ]);
    const [employeeResponse, optionResponse, departmentResponse, historyResponse] = responses;
    setEmployee(employeeResponse.data);
    setEmployeeOptions(optionResponse.data.items || []);
    setDepartments(departmentResponse.data.items || []);
    setHistory(historyResponse.data.items || []);
  };

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      employeeApi.get(id),
      employeeApi.options(),
      employeeApi.departments(),
      employeeApi.history(id),
    ])
      .then((responses) => {
        if (cancelled) return;
        const [employeeResponse, optionResponse, departmentResponse, historyResponse] = responses;
        setEmployee(employeeResponse.data);
        setEmployeeOptions(optionResponse.data.items || []);
        setDepartments(departmentResponse.data.items || []);
        setHistory(historyResponse.data.items || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.error?.message || 'Employee not found');
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  const employeeNames = useMemo(
    () => Object.fromEntries(employeeOptions.map((item) => [item.id, item.full_name])),
    [employeeOptions],
  );
  const departmentNames = useMemo(
    () => Object.fromEntries(departments.map((item) => [item.id, item.name])),
    [departments],
  );

  const update = async (payload) => {
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      await employeeApi.update(id, payload);
      await load();
      setOpen(false);
      setSuccess('Employment details updated.');
    } catch (err) {
      setError(err.error?.message || 'Employee update failed');
    } finally {
      setSaving(false);
    }
  };

  const provisionAccess = async (payload) => {
    setAccessSaving(true);
    setError('');
    setSuccess('');

    try {
      const response = await employeeApi.provisionAccess(id, payload);
      setEmployee(response.data.employee);
      setAccessOpen(false);
      setSuccess(`Access was provisioned for ${response.data.user.email}.`);
    } catch (err) {
      setError(err.error?.message || 'Access provisioning failed');
    } finally {
      setAccessSaving(false);
    }
  };

  if (error && !employee) return <Alert type="error">{error}</Alert>;
  if (!employee) return <Spinner />;

  const canProvisionAccess = hasPermission('user:create') && hasPermission('employee:update');

  return (
    <div className="space-y-6">
      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <Avatar name={employee.full_name} size="lg" />
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-bold">{employee.full_name}</h1>
                <Badge tone={employee.employment_status === 'active' ? 'green' : 'amber'}>
                  {employee.employment_status}
                </Badge>
                <Badge tone={employee.user_id ? 'blue' : 'slate'}>
                  {employee.user_id ? 'Access enabled' : 'No user access'}
                </Badge>
              </div>
              <p className="mt-1 font-medium text-cyan-700">{employee.job_title || 'Role not assigned'}</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {!employee.user_id && canProvisionAccess && employee.employment_status !== 'terminated' && (
              <Button variant="accent" onClick={() => setAccessOpen(true)}>
                <KeyRound size={16} /> Provision access
              </Button>
            )}
            {hasPermission('employee:update') && (
              <Button variant="secondary" onClick={() => setOpen(true)}>
                <Pencil size={16} /> Edit employment details
              </Button>
            )}
          </div>
        </div>

        <div className="mt-6 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
          <p><b>Email:</b> {employee.email}</p>
          <p><b>Employee no:</b> {employee.employee_number}</p>
          <p><b>Hire date:</b> {employee.hire_date}</p>
          <p><b>Department:</b> {departmentNames[employee.department_id] || 'Unassigned'}</p>
          <p><b>Work location:</b> {employee.work_location || 'Not set'}</p>
          <p className="flex items-center gap-2">
            <UserRoundCheck size={16} className="text-cyan-700" />
            <b>Reports to:</b> {employeeNames[employee.manager_id] || 'Top level'}
          </p>
        </div>
      </Card>

      <Card>
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-violet-50 text-violet-700">
            <History size={19} />
          </span>
          <div>
            <h2 className="text-lg font-bold text-slate-950">Employment history</h2>
            <p className="text-sm text-slate-500">Promotions, reporting changes and department transfers.</p>
          </div>
        </div>

        <div className="mt-5 space-y-3">
          {history.length === 0 ? (
            <p className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-500">No employment changes recorded yet.</p>
          ) : history.map((item) => (
            <div key={item.id} className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">{item.job_title || 'Unassigned role'}</p>
                  <p className="mt-1 text-sm text-slate-600">
                    {item.department_name || 'No department'}
                    {item.manager_name ? ` · Reports to ${item.manager_name}` : ' · Top level'}
                  </p>
                </div>
                <span className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
                  <CalendarClock size={14} />
                  {item.start_date}{item.end_date ? ` – ${item.end_date}` : ' – Present'}
                </span>
              </div>
              {item.reason && <p className="mt-3 text-sm text-slate-500">{item.reason}</p>}
            </div>
          ))}
        </div>
      </Card>

      <Modal
        title={`Edit ${employee.full_name}`}
        open={open}
        onClose={() => setOpen(false)}
        size="xl"
      >
        <EmployeeForm
          onSubmit={update}
          loading={saving}
          initialValues={employee}
          employees={employeeOptions}
          departments={departments}
          excludeEmployeeId={employee.id}
          submitLabel="Update employee"
          showChangeContext
        />
      </Modal>

      <Modal
        title={`Provision access for ${employee.full_name}`}
        open={accessOpen}
        onClose={() => setAccessOpen(false)}
        size="lg"
      >
        <EmployeeAccessForm
          employee={employee}
          onSubmit={provisionAccess}
          loading={accessSaving}
        />
      </Modal>
    </div>
  );
}
