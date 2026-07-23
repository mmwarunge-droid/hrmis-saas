import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { authApi } from '../api/authApi';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';

export default function VerifyEmail() {
  const location = useLocation();
  const token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
  const [message, setMessage] = useState('');
  const [error, setError] = useState(token ? '' : 'The verification link is missing its token.');
  const [loading, setLoading] = useState(false);

  const verify = async () => {
    setError('');
    setMessage('');
    if (!token) {
      setError('The verification link is missing its token.');
      return;
    }

    setLoading(true);
    try {
      const response = await authApi.confirmEmailVerification({ token });
      setMessage(response.message || 'Your email address has been verified.');
    } catch (err) {
      setError(err.error?.message || 'The verification link is invalid or has expired.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="w-full max-w-md">
      <h1 className="text-2xl font-bold">Verify your email</h1>
      <p className="mt-1 text-sm text-slate-500">Confirm this one-time link to verify your HRMIS email address.</p>
      <div className="mt-6 space-y-4">
        {message && <Alert>{message}</Alert>}
        {error && <Alert type="error">{error}</Alert>}
        <Button className="w-full" onClick={verify} disabled={loading || !token || Boolean(message)}>
          {loading ? 'Verifying...' : 'Verify email'}
        </Button>
      </div>
      <Link className="mt-4 block text-center text-sm font-medium text-slate-700 underline" to="/login">Continue to sign in</Link>
    </Card>
  );
}
