import { Navigate, Route, Routes } from 'react-router-dom';
import AuthLayout from './layouts/AuthLayout.jsx';
import DashboardLayout from './layouts/DashboardLayout.jsx';
import PermissionRoute from './routes/PermissionRoute.jsx';
import ProtectedRoute from './routes/ProtectedRoute.jsx';
import RoleRoute from './routes/RoleRoute.jsx';
import Attendance from './pages/Attendance.jsx';
import AskKinetic from './pages/AskKinetic.jsx';
import EmployeeExperienceSettings from './pages/EmployeeExperienceSettings.jsx';
import EmployeeHome from './pages/EmployeeHome.jsx';
import HomeRouter from './pages/HomeRouter.jsx';
import HelpCenter from './pages/HelpCenter.jsx';
import Goals from './pages/Goals.jsx';
import LeaveSetup from './pages/LeaveSetup.jsx';
import MyProfile from './pages/MyProfile.jsx';
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
import OrganizationEventDetails from './pages/OrganizationEventDetails.jsx';
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
          <Route path="/dashboard" element={<HomeRouter />} />
          <Route path="/employee-home" element={<EmployeeHome />} />
          <Route path="/profile" element={<MyProfile />} />
          <Route path="/ask-kinetic" element={<AskKinetic />} />
          <Route path="/ask-ace" element={<Navigate to="/ask-kinetic" replace />} />
          <Route path="/events/:id" element={<OrganizationEventDetails />} />
          <Route path="/employees" element={<Employees />} />
          <Route path="/employees/:id" element={<EmployeeDetails />} />
          <Route path="/org-chart" element={<OrgChart />} />
          <Route element={<PermissionRoute permission="employee:update" />}>
            <Route path="/departments" element={<Departments />} />
          </Route>
          <Route path="/documents" element={<Documents />} />
          <Route element={<PermissionRoute permission="document:approve" />}>
            <Route
              path="/signature-requests"
              element={<SignatureRequests />}
            />
          </Route>
          <Route path="/leave" element={<LeaveRequests />} />
          <Route element={<PermissionRoute permission="leave:approve" />}>
            <Route path="/leave/setup" element={<LeaveSetup />} />
          </Route>
          <Route path="/attendance" element={<Attendance />} />
          <Route element={<PermissionRoute permission="goal:read" />}>
            <Route path="/goals" element={<Goals />} />
          </Route>
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route element={<PermissionRoute permission="user:read" />}>
            <Route path="/users" element={<Users />} />
          </Route>
          <Route path="/settings" element={<Settings />} />
          <Route path="/help" element={<HelpCenter />} />
          <Route
            element={
              <RoleRoute
                roles={[
                  'SUPER_ADMIN',
                  'ORGANIZATION_OWNER',
                  'CLIENT_ADMIN',
                ]}
              />
            }
          >
            <Route
              path="/settings/employee-experience"
              element={<EmployeeExperienceSettings />}
            />
          </Route>
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
