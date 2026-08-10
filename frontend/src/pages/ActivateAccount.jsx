import { Eye, EyeOff, KeyRound, MailCheck } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { authApi } from '../api/authApi';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';

function PasswordField({
  id,
  label,
  value,
  onChange,
  visible,
  onToggle,
  autoComplete,
}) {
  return (
    <div className="block space-y-1.5">
      <label
        htmlFor={id}
        className="flex items-center gap-1 text-[13px] font-semibold text-slate-700 after:ml-1 after:text-red-600 after:content-['*']"
      >
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={onChange}
          autoComplete={autoComplete}
          minLength={10}
          maxLength={128}
          required
          className="min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 pr-11 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 hover:border-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
        />
        <button
          type="button"
          aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          aria-pressed={visible}
          onClick={onToggle}
          className="absolute inset-y-0 right-1 grid w-9 place-items-center rounded-md text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-100"
        >
          {visible ? (
            <EyeOff size={18} aria-hidden="true" />
          ) : (
            <Eye size={18} aria-hidden="true" />
          )}
        </button>
      </div>
    </div>
  );
}

export default function ActivateAccount() {
  const location = useLocation();
  const navigate = useNavigate();
  const token = useMemo(
    () => new URLSearchParams(location.hash.slice(1)).get('token') || '',
    [location.hash],
  );
  const [context, setContext] = useState(null);
  const [form, setForm] = useState({ password: '', confirmPassword: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [loading, setLoading] = useState(Boolean(token));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(
    token ? '' : 'This activation link is missing its secure token.',
  );

  useEffect(() => {
    let active = true;
    if (!token) return undefined;

    setLoading(true);
    authApi.validateInvitation({ token })
      .then((response) => {
        if (active) setContext(response.data);
      })
      .catch((err) => {
        if (active) {
          setError(
            err.error?.message
              || 'This invitation is invalid, expired or has already been used.',
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [token]);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      const response = await authApi.acceptInvitation({
        token,
        password: form.password,
      });
      navigate('/login?activated=1', {
        replace: true,
        state: {
          email: response.data?.email || context?.email || '',
        },
      });
    } catch (err) {
      setError(
        err.error?.message
          || 'Your account could not be activated. Request a new invitation.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="w-full max-w-lg border-white/80 p-7 shadow-2xl">
      <span className="grid h-11 w-11 place-items-center rounded-lg bg-blue-50 text-blue-700">
        <KeyRound size={20} />
      </span>
      <h1 className="mt-5 text-3xl font-bold tracking-tight text-slate-950">
        Welcome to Kinetic
      </h1>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        Create your private password to activate your account. Your
        administrator will never see this password.
      </p>

      {loading && (
        <div className="mt-6 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
          Validating your secure invitation…
        </div>
      )}

      {error && <div className="mt-6"><Alert type="error">{error}</Alert></div>}

      {!loading && context && (
        <form onSubmit={submit} className="mt-6 space-y-4">
          <div className="rounded-lg border border-blue-100 bg-blue-50/70 p-4">
            <div className="flex items-start gap-3">
              <MailCheck className="mt-0.5 shrink-0 text-blue-700" size={18} />
              <div className="min-w-0">
                <p className="font-semibold text-slate-950">
                  {context.full_name}
                </p>
                <p className="mt-1 break-all text-sm text-slate-600">
                  {context.email}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {context.organization_name}
                </p>
              </div>
            </div>
          </div>

          <PasswordField
            id="activation-password"
            label="New password"
            value={form.password}
            onChange={(event) => setForm({
              ...form,
              password: event.target.value,
            })}
            visible={showPassword}
            onToggle={() => setShowPassword((current) => !current)}
            autoComplete="new-password"
          />
          <PasswordField
            id="activation-password-confirmation"
            label="Confirm password"
            value={form.confirmPassword}
            onChange={(event) => setForm({
              ...form,
              confirmPassword: event.target.value,
            })}
            visible={showConfirmation}
            onToggle={() => setShowConfirmation((current) => !current)}
            autoComplete="new-password"
          />

          <p className="text-xs leading-5 text-slate-500">
            Use at least 10 characters. After activation, Kinetic will take
            you to sign in with the credentials you just created.
          </p>

          <Button
            variant="accent"
            size="lg"
            className="w-full"
            disabled={submitting}
          >
            {submitting ? 'Activating...' : 'Activate my account'}
          </Button>
        </form>
      )}
    </Card>
  );
}
