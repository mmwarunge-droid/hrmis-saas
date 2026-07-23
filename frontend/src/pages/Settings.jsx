import { useState } from 'react';
import { authApi } from '../api/authApi';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import useAuth from '../hooks/useAuth';

export default function Settings() {
  const { user } = useAuth();
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
    </div>
  );
}
