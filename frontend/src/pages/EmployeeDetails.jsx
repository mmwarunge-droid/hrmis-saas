import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { employeeApi } from '../api/employeeApi';
import Alert from '../components/ui/Alert.jsx';
import Card from '../components/ui/Card.jsx';
import Spinner from '../components/ui/Spinner.jsx';

export default function EmployeeDetails() {
  const { id } = useParams();
  const [employee, setEmployee] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { employeeApi.get(id).then((res) => setEmployee(res.data)).catch((err) => setError(err.error?.message || 'Employee not found')); }, [id]);
  if (error) return <Alert type="error">{error}</Alert>;
  if (!employee) return <Spinner />;
  return <Card><h1 className="text-2xl font-bold">{employee.full_name}</h1><div className="mt-4 grid gap-3 text-sm md:grid-cols-2"><p><b>Email:</b> {employee.email}</p><p><b>Employee no:</b> {employee.employee_number}</p><p><b>Job title:</b> {employee.job_title || '-'}</p><p><b>Status:</b> {employee.employment_status}</p><p><b>Hire date:</b> {employee.hire_date}</p></div></Card>;
}
