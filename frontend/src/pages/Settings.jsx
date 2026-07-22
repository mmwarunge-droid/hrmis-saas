import Card from '../components/ui/Card.jsx';
import useAuth from '../hooks/useAuth';

export default function Settings() {
  const { user } = useAuth();
  return <Card><h1 className="text-2xl font-bold">Settings</h1><p className="mt-2 text-slate-600">Current tenant: {user?.tenant_id || 'Platform'}</p><p className="text-slate-600">Environment API: {import.meta.env.VITE_API_BASE_URL}</p></Card>;
}
