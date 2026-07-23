import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Input from '../components/ui/Input.jsx';
import useAuth from '../hooks/useAuth';

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  if (user) return <Navigate to="/dashboard" replace />;
  const submit = async (e) => {
    e.preventDefault(); setError(''); setLoading(true);
    try {
      const result = await login(form);
      const destination = location.state?.from?.pathname || '/dashboard';
      if (result.mfa_required) {
        navigate('/mfa', {
          replace: true,
          state: {
            challengeToken: result.challenge_token,
            enrollmentRequired: result.mfa_enrollment_required,
            destination,
          },
        });
        return;
      }
      navigate(destination, { replace: true });
    } catch (err) { setError(err.error?.message || 'Login failed'); }
    finally { setLoading(false); }
  };
  return (
    <Card className="w-full max-w-md">
      <h1 className="text-2xl font-bold">Sign in</h1>
      <p className="mt-1 text-sm text-slate-500">Access your consulting-led HRMIS workspace.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        {error && <Alert type="error">{error}</Alert>}
        <Input label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        <Input label="Password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        <div className="text-right"><Link className="text-sm font-medium text-slate-700 underline" to="/forgot-password">Forgot password?</Link></div>
        <Button className="w-full" disabled={loading}>{loading ? 'Signing in...' : 'Sign in'}</Button>
      </form>
    </Card>
  );
}
