import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { authApi } from '../api/authApi';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Input from '../components/ui/Input.jsx';

export default function ResetPassword() {
  const location = useLocation();
  const token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
  const [form, setForm] = useState({ password: '', confirmPassword: '' });
  const [message, setMessage] = useState('');
  const [error, setError] = useState(token ? '' : 'The reset link is missing its token.');
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');
    if (!token) {
      setError('The reset link is missing its token.');
      return;
    }
    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const response = await authApi.resetPassword({ token, password: form.password });
      setMessage(response.message || 'Your password has been reset.');
      setForm({ password: '', confirmPassword: '' });
    } catch (err) {
      setError(err.error?.message || 'The reset link is invalid or has expired.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="w-full max-w-md">
      <h1 className="text-2xl font-bold">Choose a new password</h1>
      <p className="mt-1 text-sm text-slate-500">Use at least 10 characters and avoid reusing your current password.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        {message && <Alert>{message}</Alert>}
        {error && <Alert type="error">{error}</Alert>}
        <Input
          label="New password"
          type="password"
          minLength={10}
          value={form.password}
          onChange={(event) => setForm({ ...form, password: event.target.value })}
          required
        />
        <Input
          label="Confirm password"
          type="password"
          minLength={10}
          value={form.confirmPassword}
          onChange={(event) => setForm({ ...form, confirmPassword: event.target.value })}
          required
        />
        <Button className="w-full" disabled={loading || !token || Boolean(message)}>{loading ? 'Resetting...' : 'Reset password'}</Button>
      </form>
      <Link className="mt-4 block text-center text-sm font-medium text-slate-700 underline" to="/login">Back to sign in</Link>
    </Card>
  );
}
