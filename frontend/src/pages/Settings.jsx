import { useEffect, useState } from 'react';
import { authApi } from '../api/authApi';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Input from '../components/ui/Input.jsx';
import useAuth from '../hooks/useAuth';

export default function Settings() {
  const { user } = useAuth();
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [mfa, setMfa] = useState(null);
  const [mfaCode, setMfaCode] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState([]);

  useEffect(() => {
    authApi.mfaStatus().then((response) => setMfa(response.data)).catch(() => setMfa(null));
  }, []);

  const requestVerification = async () => {
    setMessage('');
    setError('');
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

  const regenerateRecoveryCodes = async (event) => {
    event.preventDefault();
    setMessage('');
    setError('');
    setLoading(true);
    try {
      const response = await authApi.regenerateMfaRecoveryCodes({ code: mfaCode });
      setRecoveryCodes(response.data.recovery_codes || []);
      setMfa((current) => ({ ...current, recovery_codes_remaining: response.data.recovery_codes?.length || 0 }));
      setMfaCode('');
    } catch (err) {
      setError(err.error?.message || 'Recovery codes could not be regenerated.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="mt-2 text-slate-600">Current tenant: {user?.tenant_id || 'Platform'}</p>
        <p className="text-slate-600">Environment API: {import.meta.env.VITE_API_BASE_URL}</p>
      </Card>
      <Card>
        <h2 className="text-lg font-semibold">Email verification</h2>
        <p className="mt-1 text-sm text-slate-600">
          {user?.email_verified ? 'Your email address is verified.' : 'Verify your email before enabling privileged recovery controls.'}
        </p>
        <div className="mt-4 space-y-3">
          {message && <Alert>{message}</Alert>}
          {error && <Alert type="error">{error}</Alert>}
          {!user?.email_verified && (
            <Button onClick={requestVerification} disabled={loading}>
              {loading ? 'Sending...' : 'Send verification email'}
            </Button>
          )}
        </div>
      </Card>
      <Card>
        <h2 className="text-lg font-semibold">Multi-factor authentication</h2>
        <p className="mt-1 text-sm text-slate-600">
          {mfa?.enabled ? 'Authenticator MFA is enabled.' : mfa?.required ? 'MFA is required for your privileged role.' : 'MFA is not enabled.'}
        </p>
        {mfa?.enabled && (
          <form onSubmit={regenerateRecoveryCodes} className="mt-4 max-w-md space-y-3">
            <p className="text-sm text-slate-600">Unused recovery codes: {mfa.recovery_codes_remaining}</p>
            <Input label="Current authenticator code" value={mfaCode} onChange={(event) => setMfaCode(event.target.value)} required />
            <Button disabled={loading}>{loading ? 'Regenerating...' : 'Regenerate recovery codes'}</Button>
          </form>
        )}
        {recoveryCodes.length > 0 && (
          <div className="mt-4 grid max-w-md grid-cols-2 gap-2 rounded-xl bg-slate-100 p-4 font-mono text-sm">
            {recoveryCodes.map((code) => <span key={code}>{code}</span>)}
          </div>
        )}
      </Card>
    </div>
  );
}
