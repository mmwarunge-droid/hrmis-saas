import { useEffect, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { authApi } from '../api/authApi';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Input from '../components/ui/Input.jsx';
import useAuth from '../hooks/useAuth';

export default function MfaChallenge() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, confirmMfaEnrollment, verifyMfaChallenge } = useAuth();
  const challengeToken = location.state?.challengeToken;
  const enrollmentRequired = Boolean(location.state?.enrollmentRequired);
  const destination = location.state?.destination || '/dashboard';
  const [enrollment, setEnrollment] = useState(null);
  const [code, setCode] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(enrollmentRequired);

  useEffect(() => {
    if (!challengeToken || !enrollmentRequired) return;
    let active = true;
    authApi.startMfaEnrollment({ challenge_token: challengeToken })
      .then((response) => { if (active) setEnrollment(response.data); })
      .catch((err) => { if (active) setError(err.error?.message || 'MFA enrollment could not be started.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [challengeToken, enrollmentRequired]);

  if (user && !enrollmentRequired) return <Navigate to={destination} replace />;
  if (!challengeToken) return <Navigate to="/login" replace />;

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const payload = { challenge_token: challengeToken, code };
      if (enrollmentRequired) {
        const result = await confirmMfaEnrollment(payload);
        setRecoveryCodes(result.recovery_codes || []);
      } else {
        await verifyMfaChallenge(payload);
        navigate(destination, { replace: true });
      }
    } catch (err) {
      setError(err.error?.message || 'The authentication code was not accepted.');
    } finally {
      setLoading(false);
    }
  };

  if (recoveryCodes.length > 0) {
    return (
      <Card className="w-full max-w-lg">
        <h1 className="text-2xl font-bold">Save your recovery codes</h1>
        <Alert>Each code works once. Store them somewhere separate from your authenticator.</Alert>
        <div className="mt-4 grid grid-cols-2 gap-2 rounded-xl bg-slate-100 p-4 font-mono text-sm">
          {recoveryCodes.map((recoveryCode) => <span key={recoveryCode}>{recoveryCode}</span>)}
        </div>
        <Button className="mt-5 w-full" onClick={() => navigate(destination, { replace: true })}>Continue</Button>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-lg">
      <h1 className="text-2xl font-bold">{enrollmentRequired ? 'Set up multi-factor authentication' : 'Enter your authentication code'}</h1>
      <p className="mt-1 text-sm text-slate-500">
        {enrollmentRequired ? 'Privileged accounts must use an authenticator app.' : 'Use your authenticator code or a single-use recovery code.'}
      </p>
      {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
      {enrollmentRequired && enrollment && (
        <div className="mt-5 space-y-3">
          <img className="mx-auto h-52 w-52" src={enrollment.qr_code_data_uri} alt="Authenticator QR code" />
          <p className="text-center text-xs text-slate-500">Manual key</p>
          <p className="break-all rounded-lg bg-slate-100 p-3 text-center font-mono text-sm">{enrollment.manual_key}</p>
        </div>
      )}
      <form onSubmit={submit} className="mt-5 space-y-4">
        <Input
          label={enrollmentRequired ? 'Six-digit authenticator code' : 'Authenticator or recovery code'}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          autoComplete="one-time-code"
          inputMode={enrollmentRequired ? 'numeric' : undefined}
          required
        />
        <Button className="w-full" disabled={loading || (enrollmentRequired && !enrollment)}>
          {loading ? 'Verifying...' : enrollmentRequired ? 'Enable MFA' : 'Verify'}
        </Button>
      </form>
    </Card>
  );
}
