import { ArrowRight, LockKeyhole } from 'lucide-react';
import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
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

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = await login(form);
      const destination = '/dashboard';
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
    } catch (err) {
      setError(err.error?.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="w-full border-white/80 p-7 shadow-2xl">
      <span className="grid h-11 w-11 place-items-center rounded-2xl bg-cyan-50 text-cyan-700"><LockKeyhole size={20} /></span>
      <h1 className="mt-5 text-3xl font-bold tracking-tight text-slate-950">Welcome back</h1>
      <p className="mt-2 text-sm leading-6 text-slate-500">Sign in to your organization’s people workspace.</p>
      <form onSubmit={submit} className="mt-7 space-y-4">
        {error && <Alert type="error">{error}</Alert>}
        <Input label="Work email" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} autoComplete="email" required />
        <Input label="Password" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} autoComplete="current-password" required />
        <div className="text-right"><Link className="text-sm font-semibold text-cyan-700 hover:text-cyan-900" to="/forgot-password">Forgot password?</Link></div>
        <Button variant="accent" className="w-full" size="lg" disabled={loading}>{loading ? 'Signing in...' : <>Sign in <ArrowRight size={17} /></>}</Button>
      </form>
      <p className="mt-5 text-center text-xs text-slate-400">Protected by secure cookies, CSRF controls and privileged-role MFA.</p>
    </Card>
  );
}
