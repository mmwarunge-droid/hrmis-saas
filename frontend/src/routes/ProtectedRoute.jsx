import { Navigate, Outlet, useLocation } from 'react-router-dom';
import Spinner from '../components/ui/Spinner.jsx';
import useAuth from '../hooks/useAuth';

export default function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="min-h-screen grid place-items-center"><Spinner /></div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <Outlet />;
}
