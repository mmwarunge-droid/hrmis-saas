import { useEffect, useMemo, useState } from 'react';
import { tenantApi } from '../../api/tenantApi.js';
import { userApi } from '../../api/userApi.js';
import Alert from '../ui/Alert.jsx';
import Badge from '../ui/Badge.jsx';
import Button from '../ui/Button.jsx';
import Card from '../ui/Card.jsx';
import Input from '../ui/Input.jsx';
import Table from '../ui/Table.jsx';

function statusTone(item) {
  if (item.compliant) return 'green';
  if (item.in_grace_period) return 'amber';
  return 'red';
}

function statusLabel(item) {
  if (item.mfa_enabled) return 'Enabled';
  if (item.in_grace_period) return 'Grace period';
  if (item.required) return 'Required';
  return 'Optional';
}

export default function MfaPolicyPanel({
  tenantId,
  currentUserId,
}) {
  const [policy, setPolicy] = useState(null);
  const [compliance, setCompliance] = useState(null);
  const [mode, setMode] = useState('optional');
  const [graceDays, setGraceDays] = useState('14');
  const [enforcementDate, setEnforcementDate] = useState('');
  const [resetTarget, setResetTarget] = useState(null);
  const [resetReason, setResetReason] = useState('');
  const [resetPassword, setResetPassword] = useState('');
  const [resetCode, setResetCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = () => Promise.all([
    tenantApi.mfaPolicy(tenantId),
    tenantApi.mfaCompliance(tenantId),
  ]).then(([policyResponse, complianceResponse]) => {
    const nextPolicy = policyResponse.data;
    setPolicy(nextPolicy);
    setCompliance(complianceResponse.data);
    setMode(nextPolicy.mode);
    setGraceDays(String(nextPolicy.grace_days));
    setEnforcementDate(nextPolicy.enforcement_date || '');
  });

  useEffect(() => {
    let active = true;
    Promise.all([
      tenantApi.mfaPolicy(tenantId),
      tenantApi.mfaCompliance(tenantId),
    ])
      .then(([policyResponse, complianceResponse]) => {
        if (!active) return;
        const nextPolicy = policyResponse.data;
        setPolicy(nextPolicy);
        setCompliance(complianceResponse.data);
        setMode(nextPolicy.mode);
        setGraceDays(String(nextPolicy.grace_days));
        setEnforcementDate(nextPolicy.enforcement_date || '');
      })
      .catch((err) => {
        if (active) {
          setError(err.error?.message || 'Unable to load MFA policy.');
        }
      });
    return () => {
      active = false;
    };
  }, [tenantId]);

  const savePolicy = async (event) => {
    event.preventDefault();
    setLoading(true);
    setMessage('');
    setError('');
    try {
      const response = await tenantApi.updateMfaPolicy(
        tenantId,
        {
          mode,
          grace_days: Number(graceDays),
          enforcement_date: mode === 'optional'
            ? null
            : enforcementDate || null,
        },
      );
      setPolicy(response.data);
      setEnforcementDate(response.data.enforcement_date || '');
      setMessage(response.message || 'MFA policy updated.');
      const complianceResponse = await tenantApi.mfaCompliance(tenantId);
      setCompliance(complianceResponse.data);
    } catch (err) {
      setError(err.error?.message || 'MFA policy could not be updated.');
    } finally {
      setLoading(false);
    }
  };

  const resetMfa = async (event) => {
    event.preventDefault();
    if (!resetTarget) return;
    setLoading(true);
    setMessage('');
    setError('');
    try {
      const response = await userApi.resetMfa(
        resetTarget.id,
        { reason: resetReason },
      );
      setMessage(response.message || 'MFA enrollment reset.');
      setResetTarget(null);
      setResetReason('');
      setResetPassword('');
      setResetCode('');
      await load();
    } catch (err) {
      setError(err.error?.message || 'MFA enrollment could not be reset.');
    } finally {
      setLoading(false);
    }
  };

  const columns = useMemo(() => [
    {
      key: 'person',
      label: 'Person',
      render: (item) => (
        <div>
          <p className="font-semibold text-slate-900">{item.full_name}</p>
          <p className="text-xs text-slate-500">{item.email}</p>
        </div>
      ),
    },
    {
      key: 'roles',
      label: 'Access',
      render: (item) => (
        <div className="flex flex-wrap gap-1">
          {item.roles.map((role) => (
            <Badge key={role} tone="blue">
              {role.replaceAll('_', ' ')}
            </Badge>
          ))}
        </div>
      ),
    },
    {
      key: 'mfa',
      label: 'MFA',
      render: (item) => (
        <Badge tone={statusTone(item)}>
          {statusLabel(item)}
        </Badge>
      ),
    },
    {
      key: 'enforcement',
      label: 'Enforcement',
      render: (item) => (
        <span className="text-sm text-slate-600">
          {item.enforcement_date || 'Platform floor or optional'}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Recovery',
      render: (item) => (
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={
            !item.mfa_enabled
            || item.id === currentUserId
          }
          onClick={() => {
            setResetTarget(item);
            setResetReason('');
          }}
        >
          Reset MFA
        </Button>
      ),
    },
  ], [currentUserId]);

  if (!policy || !compliance) {
    return (
      <Card>
        <h2 className="text-lg font-semibold">Organization MFA policy</h2>
        {error
          ? <div className="mt-3"><Alert type="error">{error}</Alert></div>
          : <p className="mt-2 text-sm text-slate-500">Loading security policy…</p>}
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <div>
          <h2 className="text-lg font-semibold">Organization MFA policy</h2>
          <p className="mt-1 text-sm text-slate-600">
            Schedule authenticator enforcement without using email as a sign-in factor.
          </p>
        </div>

        {message && <div className="mt-4"><Alert type="success">{message}</Alert></div>}
        {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}

        <form onSubmit={savePolicy} className="mt-5 grid gap-4 lg:grid-cols-3">
          <label className="space-y-1 text-sm font-medium text-slate-700">
            <span>Policy mode</span>
            <select
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5"
              value={mode}
              onChange={(event) => setMode(event.target.value)}
            >
              {policy.modes.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <Input
            label="Enrollment grace days"
            type="number"
            min="0"
            max="365"
            value={graceDays}
            onChange={(event) => setGraceDays(event.target.value)}
            required
          />

          <Input
            label="Enforcement date"
            type="date"
            value={enforcementDate}
            onChange={(event) => setEnforcementDate(event.target.value)}
            disabled={mode === 'optional'}
          />

          <div className="lg:col-span-3">
            <p className="mb-3 text-sm text-slate-600">
              {policy.modes.find((item) => item.value === mode)?.description}
            </p>
            <Button disabled={loading}>
              {loading ? 'Saving…' : 'Save MFA policy'}
            </Button>
          </div>
        </form>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ['Users', compliance.summary.total_users],
          ['MFA enabled', compliance.summary.enabled_users],
          ['MFA required', compliance.summary.required_users],
          ['Non-compliant', compliance.summary.noncompliant_users],
        ].map(([label, value]) => (
          <Card key={label}>
            <p className="text-sm text-slate-500">{label}</p>
            <p className="mt-2 text-3xl font-bold text-slate-950">{value}</p>
          </Card>
        ))}
      </div>

      <Table
        columns={columns}
        rows={compliance.items}
        empty="No active user accounts found."
      />

      {resetTarget && (
        <Card>
          <form onSubmit={resetMfa} className="max-w-xl space-y-4">
            <div>
              <h3 className="font-semibold text-slate-950">
                Reset MFA for {resetTarget.full_name}
              </h3>
              <p className="mt-1 text-sm text-slate-600">
                This clears the authenticator and recovery codes, revokes every session,
                and requires re-enrollment when policy applies.
              </p>
            </div>
            <Input
              label="Your current password"
              type="password"
              value={resetPassword}
              onChange={(event) => setResetPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
            <Input
              label="Your authenticator code"
              value={resetCode}
              onChange={(event) => setResetCode(event.target.value)}
              autoComplete="one-time-code"
              inputMode="numeric"
              required
            />
            <label className="block space-y-1 text-sm font-medium text-slate-700">
              <span>Administrative reason</span>
              <textarea
                className="min-h-24 w-full rounded-2xl border border-slate-200 px-4 py-3"
                value={resetReason}
                onChange={(event) => setResetReason(event.target.value)}
                required
                minLength={5}
              />
            </label>
            <div className="flex gap-2">
              <Button variant="danger" disabled={loading}>
                {loading ? 'Resetting…' : 'Reset MFA and revoke sessions'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setResetTarget(null);
                  setResetPassword('');
                  setResetCode('');
                }}
                disabled={loading}
              >
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}
    </div>
  );
}
