import { useEffect, useState } from 'react';
import { authApi } from '../api/authApi';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Input from '../components/ui/Input.jsx';
import useAuth from '../hooks/useAuth';

function RecoveryCodes({ codes, onCopy }) {
  if (!codes.length) return null;
  return (
    <div className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50 p-4">
      <div>
        <h3 className="font-semibold text-amber-950">Save these recovery codes now</h3>
        <p className="text-sm text-amber-800">
          Each code works once. Store them separately from your authenticator.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-2 rounded-xl bg-white p-4 font-mono text-sm">
        {codes.map((code) => <span key={code}>{code}</span>)}
      </div>
      <Button type="button" variant="secondary" onClick={onCopy}>
        Copy recovery codes
      </Button>
    </div>
  );
}

export default function Settings() {
  const { user } = useAuth();
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [mfa, setMfa] = useState(null);
  const [enrollment, setEnrollment] = useState(null);
  const [enrollmentPassword, setEnrollmentPassword] = useState('');
  const [enrollmentCode, setEnrollmentCode] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [disablePassword, setDisablePassword] = useState('');
  const [disableCode, setDisableCode] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState([]);

  useEffect(() => {
    let active = true;
    authApi.mfaStatus()
      .then((response) => {
        if (active) setMfa(response.data);
      })
      .catch(() => {
        if (active) setMfa(null);
      });
    return () => {
      active = false;
    };
  }, []);

  const clearFeedback = () => {
    setMessage('');
    setError('');
  };

  const requestVerification = async () => {
    clearFeedback();
    setLoading(true);
    try {
      const response = await authApi.requestEmailVerification();
      setMessage(response.message || 'Verification instructions sent.');
    } catch (err) {
      setError(err.error?.message || 'Verification email could not be sent.');
    } finally {
      setLoading(false);
    }
  };

  const startEnrollment = async (event) => {
    event.preventDefault();
    clearFeedback();
    setRecoveryCodes([]);
    setLoading(true);
    try {
      const response = await authApi.startSelfMfaEnrollment({
        password: enrollmentPassword,
      });
      setEnrollment(response.data);
      setEnrollmentCode('');
      setEnrollmentPassword('');
    } catch (err) {
      setError(err.error?.message || 'Authenticator enrollment could not be started.');
    } finally {
      setLoading(false);
    }
  };

  const confirmEnrollment = async (event) => {
    event.preventDefault();
    clearFeedback();
    setLoading(true);
    try {
      const response = await authApi.confirmSelfMfaEnrollment({
        challenge_token: enrollment.challenge_token,
        code: enrollmentCode,
      });
      setRecoveryCodes(response.data.recovery_codes || []);
      setMfa(response.data.mfa);
      setEnrollment(null);
      setEnrollmentCode('');
      setMessage(response.message || 'Multi-factor authentication enabled.');
    } catch (err) {
      setError(err.error?.message || 'The authenticator code was not accepted.');
    } finally {
      setLoading(false);
    }
  };

  const regenerateRecoveryCodes = async (event) => {
    event.preventDefault();
    clearFeedback();
    setLoading(true);
    try {
      const response = await authApi.regenerateMfaRecoveryCodes({ code: mfaCode });
      const codes = response.data.recovery_codes || [];
      setRecoveryCodes(codes);
      setMfa((current) => ({
        ...current,
        recovery_codes_remaining: codes.length,
        recovery_codes_low: codes.length <= 2,
      }));
      setMfaCode('');
      setMessage(response.message || 'Recovery codes regenerated.');
    } catch (err) {
      setError(err.error?.message || 'Recovery codes could not be regenerated.');
    } finally {
      setLoading(false);
    }
  };

  const disableMfa = async (event) => {
    event.preventDefault();
    clearFeedback();
    setLoading(true);
    try {
      await authApi.disableMfa({
        password: disablePassword,
        code: disableCode,
      });
      window.location.assign('/login');
    } catch (err) {
      setError(err.error?.message || 'Multi-factor authentication could not be disabled.');
      setLoading(false);
    }
  };

  const copyRecoveryCodes = async () => {
    try {
      await navigator.clipboard.writeText(recoveryCodes.join('\n'));
      setMessage('Recovery codes copied.');
    } catch {
      setError('Copy failed. Select and save the codes manually.');
    }
  };

  const policy = mfa?.policy || {};
  const graceMessage = policy.in_grace_period
    ? `Enrollment will be enforced in ${policy.days_until_enforcement} day${policy.days_until_enforcement === 1 ? '' : 's'}.`
    : '';

  return (
    <div className="space-y-4">
      <Card>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="mt-2 text-slate-600">Current tenant: {user?.tenant_id || 'Platform'}</p>
        <p className="text-slate-600">Environment API: {import.meta.env.VITE_API_BASE_URL}</p>
      </Card>

      {message && <Alert type="success">{message}</Alert>}
      {error && <Alert type="error">{error}</Alert>}

      <Card>
        <h2 className="text-lg font-semibold">Email verification</h2>
        <p className="mt-1 text-sm text-slate-600">
          {mfa?.email_verified
            ? 'Your email address is verified.'
            : 'Verify your email before enrolling an authenticator.'}
        </p>
        {!mfa?.email_verified && (
          <Button className="mt-4" onClick={requestVerification} disabled={loading}>
            {loading ? 'Sending...' : 'Send verification email'}
          </Button>
        )}
      </Card>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Multi-factor authentication</h2>
            <p className="mt-1 text-sm text-slate-600">
              {mfa?.enabled
                ? 'Authenticator MFA is enabled.'
                : mfa?.required
                  ? 'MFA is required before your next authenticated session.'
                  : 'Add an authenticator for stronger account security.'}
            </p>
            {graceMessage && <p className="mt-1 text-sm font-medium text-amber-700">{graceMessage}</p>}
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${mfa?.enabled ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700'}`}>
            {mfa?.enabled ? 'Enabled' : 'Not enabled'}
          </span>
        </div>

        {!mfa?.enabled && !enrollment && (
          <form onSubmit={startEnrollment} className="mt-5 max-w-md space-y-3">
            <Input
              label="Current password"
              type="password"
              value={enrollmentPassword}
              onChange={(event) => setEnrollmentPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
            <Button disabled={loading || !mfa?.email_verified}>
              {loading ? 'Starting...' : 'Set up authenticator'}
            </Button>
          </form>
        )}

        {!mfa?.enabled && enrollment && (
          <div className="mt-5 max-w-lg space-y-4">
            <div className="rounded-2xl border border-slate-200 p-4">
              <img
                className="mx-auto h-52 w-52"
                src={enrollment.qr_code_data_uri}
                alt="Authenticator QR code"
              />
              <p className="mt-3 text-center text-xs text-slate-500">Manual setup key</p>
              <p className="break-all rounded-lg bg-slate-100 p-3 text-center font-mono text-sm">
                {enrollment.manual_key}
              </p>
            </div>
            <form onSubmit={confirmEnrollment} className="space-y-3">
              <Input
                label="Six-digit authenticator code"
                value={enrollmentCode}
                onChange={(event) => setEnrollmentCode(event.target.value)}
                autoComplete="one-time-code"
                inputMode="numeric"
                required
              />
              <div className="flex gap-2">
                <Button disabled={loading}>
                  {loading ? 'Verifying...' : 'Enable MFA'}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setEnrollment(null)}
                  disabled={loading}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        )}

        {mfa?.enabled && (
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <form onSubmit={regenerateRecoveryCodes} className="space-y-3">
              <h3 className="font-semibold">Recovery codes</h3>
              <p className="text-sm text-slate-600">
                Unused recovery codes: {mfa.recovery_codes_remaining}
              </p>
              {mfa.recovery_codes_low && (
                <Alert>
                  Recovery codes are running low. Regenerate a new set.
                </Alert>
              )}
              <Input
                label="Current authenticator code"
                value={mfaCode}
                onChange={(event) => setMfaCode(event.target.value)}
                required
              />
              <Button disabled={loading}>
                {loading ? 'Regenerating...' : 'Regenerate recovery codes'}
              </Button>
            </form>

            {policy.can_disable && (
              <form onSubmit={disableMfa} className="space-y-3">
                <h3 className="font-semibold">Disable MFA</h3>
                <p className="text-sm text-slate-600">
                  This signs out every session. You will need to sign in again.
                </p>
                <Input
                  label="Current password"
                  type="password"
                  value={disablePassword}
                  onChange={(event) => setDisablePassword(event.target.value)}
                  required
                />
                <Input
                  label="Current authenticator code"
                  value={disableCode}
                  onChange={(event) => setDisableCode(event.target.value)}
                  required
                />
                <Button variant="danger" disabled={loading}>
                  Disable MFA
                </Button>
              </form>
            )}
          </div>
        )}
      </Card>

      <RecoveryCodes codes={recoveryCodes} onCopy={copyRecoveryCodes} />
    </div>
  );
}
