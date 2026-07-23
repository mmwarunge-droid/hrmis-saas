import { useState } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../api/authApi';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Input from '../components/ui/Input.jsx';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');
    setLoading(true);
    try {
      const response = await authApi.forgotPassword({ email });
      setMessage(response.message || 'If the account exists, password reset instructions will be sent.');
    } catch (err) {
      setError(err.error?.message || 'The request could not be processed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="w-full max-w-md">
      <h1 className="text-2xl font-bold">Reset your password</h1>
      <p className="mt-1 text-sm text-slate-500">Enter your work email to receive a single-use reset link.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        {message && <Alert>{message}</Alert>}
        {error && <Alert type="error">{error}</Alert>}
        <Input label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <Button className="w-full" disabled={loading}>{loading ? 'Sending...' : 'Send reset link'}</Button>
      </form>
      <Link className="mt-4 block text-center text-sm font-medium text-slate-700 underline" to="/login">Back to sign in</Link>
    </Card>
  );
}
