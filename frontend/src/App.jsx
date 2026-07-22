import { Navigate, Route, Routes } from 'react-router-dom';
import AuthLayout from './layouts/AuthLayout.jsx';
import DashboardLayout from './layouts/DashboardLayout.jsx';
import ProtectedRoute from './routes/ProtectedRoute.jsx';
import Attendance from './pages/Attendance.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Documents from './pages/Documents.jsx';
import EmployeeDetails from './pages/EmployeeDetails.jsx';
import Employees from './pages/Employees.jsx';
import LeaveRequests from './pages/LeaveRequests.jsx';
import Login from './pages/Login.jsx';
import Onboarding from './pages/Onboarding.jsx';
import Settings from './pages/Settings.jsx';
import Unauthorized from './pages/Unauthorized.jsx';
import Users from './pages/Users.jsx';

export default function App() {
  return (
    <Routes>
      <Route element={<AuthLayout />}><Route path="/login" element={<Login />} /></Route>
      <Route element={<ProtectedRoute />}>
        <Route element={<DashboardLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/employees" element={<Employees />} />
          <Route path="/employees/:id" element={<EmployeeDetails />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/leave" element={<LeaveRequests />} />
          <Route path="/attendance" element={<Attendance />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/users" element={<Users />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Route>
      <Route path="/unauthorized" element={<Unauthorized />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
