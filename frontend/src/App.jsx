import { Navigate, Route, Routes } from 'react-router-dom';
import AuthLayout from './layouts/AuthLayout.jsx';
import DashboardLayout from './layouts/DashboardLayout.jsx';
import ProtectedRoute from './routes/ProtectedRoute.jsx';
import RoleRoute from './routes/RoleRoute.jsx';
import Attendance from './pages/Attendance.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Departments from './pages/Departments.jsx';
import Documents from './pages/Documents.jsx';
import EmployeeDetails from './pages/EmployeeDetails.jsx';
import Employees from './pages/Employees.jsx';
import ForgotPassword from './pages/ForgotPassword.jsx';
import LeaveRequests from './pages/LeaveRequests.jsx';
import Login from './pages/Login.jsx';
import MfaChallenge from './pages/MfaChallenge.jsx';
import Onboarding from './pages/Onboarding.jsx';
import Organizations from './pages/Organizations.jsx';
import OrgChart from './pages/OrgChart.jsx';
import ResetPassword from './pages/ResetPassword.jsx';
import Settings from './pages/Settings.jsx';
import SignatureRequests from './pages/SignatureRequests.jsx';
import Tasks from './pages/Tasks.jsx';
import Unauthorized from './pages/Unauthorized.jsx';
import Users from './pages/Users.jsx';
import VerifyEmail from './pages/VerifyEmail.jsx';

export default function App() {
  return (
    <Routes>
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<Login />} />
        <Route path="/mfa" element={<MfaChallenge />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route element={<DashboardLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/employees" element={<Employees />} />
          <Route path="/employees/:id" element={<EmployeeDetails />} />
          <Route path="/org-chart" element={<OrgChart />} />
          <Route path="/departments" element={<Departments />} />
          <Route path="/documents" element={<Documents />} />
          <Route
            path="/signature-requests"
            element={<SignatureRequests />}
          />
          <Route path="/leave" element={<LeaveRequests />} />
          <Route path="/attendance" element={<Attendance />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/users" element={<Users />} />
          <Route path="/settings" element={<Settings />} />
          <Route element={<RoleRoute roles={['SUPER_ADMIN']} />}>
            <Route path="/organizations" element={<Organizations />} />
          </Route>
        </Route>
      </Route>
      <Route path="/unauthorized" element={<Unauthorized />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
