import { ArrowRight, Eye, EyeOff, LockKeyhole } from 'lucide-react';
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
  const [form, setForm] = useState({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
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
      <span className="grid h-11 w-11 place-items-center rounded-lg bg-blue-50 text-blue-700"><LockKeyhole size={20} /></span>
      <h1 className="mt-5 text-3xl font-bold tracking-tight text-slate-950">Welcome back</h1>
      <p className="mt-2 text-sm leading-6 text-slate-600">Sign in to your organization’s people workspace.</p>
      <form onSubmit={submit} className="mt-7 space-y-4">
        {error && <Alert type="error">{error}</Alert>}
        <Input label="Work email" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} autoComplete="email" required />

        <div className="block space-y-1.5">
          <label
            htmlFor="login-password"
            className="flex items-center gap-1 text-[13px] font-semibold text-slate-700 after:ml-1 after:text-red-600 after:content-['*']"
          >
            Password
          </label>
          <div className="relative">
            <input
              id="login-password"
              type={showPassword ? 'text' : 'password'}
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              autoComplete="current-password"
              required
              className="min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 pr-11 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 hover:border-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
            />
            <button
              type="button"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((current) => !current)}
              className="absolute inset-y-0 right-1 grid w-9 place-items-center rounded-md text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-100"
            >
              {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
            </button>
          </div>
        </div>

        <div className="text-right"><Link className="text-sm font-semibold text-blue-700 hover:text-blue-900" to="/forgot-password">Forgot password?</Link></div>
        <Button variant="accent" className="w-full" size="lg" disabled={loading}>{loading ? 'Signing in...' : <>Sign in <ArrowRight size={17} /></>}</Button>
      </form>
      <p className="mt-5 text-center text-xs text-slate-500">Protected by secure cookies, CSRF controls and privileged-role MFA.</p>
    </Card>
  );
}
