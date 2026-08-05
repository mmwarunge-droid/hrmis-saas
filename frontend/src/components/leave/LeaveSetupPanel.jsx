import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  CheckCircle2,
  CircleAlert,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

import Alert from '../ui/Alert.jsx';
import Badge from '../ui/Badge.jsx';
import Button from '../ui/Button.jsx';
import Card from '../ui/Card.jsx';

function policyState(pack) {
  return (pack || []).map((item) => ({
    ...item,
    annual_entitlement_days: String(
      item.annual_entitlement_days ?? 0,
    ),
    pay_percentage: String(item.pay_percentage ?? 100),
    carryover_expiry_months: (
      item.carryover_expiry_months == null
        ? ''
        : String(item.carryover_expiry_months)
    ),
  }));
}

export default function LeaveSetupPanel({
  setup,
  onSaveGovernance,
  onApplyPack,
  onInitializeBalances,
  onRunAccruals,
  loading,
}) {
  const [ownerId, setOwnerId] = useState(
    () => setup?.organization_owner?.id || '',
  );
  const [alternateId, setAlternateId] = useState(
    () => setup?.alternate_approver?.id || '',
  );
  const [policies, setPolicies] = useState(
    () => policyState(setup?.standard_pack),
  );

  const missingCodes = useMemo(
    () => new Set(
      (setup?.missing_requirements || []).map(
        (item) => item.code,
      ),
    ),
    [setup],
  );

  const updatePolicy = (index, field, value) => {
    setPolicies((current) => current.map(
      (policy, policyIndex) => (
        policyIndex === index
          ? { ...policy, [field]: value }
          : policy
      ),
    ));
  };

  const saveGovernance = (event) => {
    event.preventDefault();
    onSaveGovernance({
      organization_owner_user_id: ownerId,
      alternate_approver_user_id: alternateId,
    });
  };

  const applyPack = () => {
    onApplyPack({
      initialize_balances: true,
      policies: policies.map((policy) => ({
        ...policy,
        annual_entitlement_days: Number(
          policy.annual_entitlement_days || 0,
        ),
        pay_percentage: Number(
          policy.pay_percentage || 0,
        ),
        carryover_expiry_months: (
          policy.carryover_expiry_months === ''
            ? null
            : Number(policy.carryover_expiry_months)
        ),
      })),
    });
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {[
          {
            code: 'employee_profile',
            label: 'Your employee profile',
          },
          {
            code: 'leave_policies',
            label: 'Policy pack',
          },
          {
            code: 'approval_governance',
            label: 'Approval governance',
          },
          {
            code: 'opening_balances',
            label: 'Opening balances',
          },
        ].map((step) => {
          const incomplete = step.code === 'approval_governance'
            ? (
              missingCodes.has('organization_owner')
              || missingCodes.has('alternate_approver')
            )
            : missingCodes.has(step.code);
          return (
            <Card key={step.code} className="p-4">
              <div className="flex items-center gap-3">
                {incomplete
                  ? <CircleAlert className="text-amber-500" size={20} />
                  : <CheckCircle2 className="text-emerald-500" size={20} />}
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    {step.label}
                  </p>
                  <Badge tone={incomplete ? 'amber' : 'green'}>
                    {incomplete ? 'Action required' : 'Ready'}
                  </Badge>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {missingCodes.has('employee_profile') && (
        <Alert
          type="warning"
          title="Your login is not linked to an employee record"
        >
          <p>
            Organization policy and approval configuration can still be
            completed. This requirement only blocks this account from
            requesting its own time off. Create or locate your employee record
            and link it to the existing user account.
          </p>
          <Link
            to="/employees"
            className="mt-2 inline-flex font-bold text-amber-950 underline underline-offset-2"
          >
            Open People directory
          </Link>
        </Alert>
      )}

      <Card>
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-1 text-blue-600" size={22} />
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
              Approval governance
            </p>
            <h3 className="mt-1 text-lg font-bold text-slate-950">
              Assign the business owner and alternate approver
            </h3>
            <p className="mt-1 text-sm text-slate-600">
              HR and client-administrator requests route to the business
              owner. The owner’s own requests route to the alternate.
            </p>
          </div>
        </div>

        <form
          onSubmit={saveGovernance}
          className="mt-5 grid gap-4 md:grid-cols-2"
        >
          <label className="block space-y-1">
            <span className="text-sm font-medium text-slate-700">
              Business owner
            </span>
            <select
              aria-label="Business owner"
              value={ownerId}
              onChange={(event) => setOwnerId(event.target.value)}
              className="w-full rounded-xl border border-slate-200 px-3 py-2"
              required
            >
              <option value="">Select owner</option>
              {(setup?.governance_candidates || []).map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.full_name}
                  {candidate.job_title ? ` — ${candidate.job_title}` : ''}
                </option>
              ))}
            </select>
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium text-slate-700">
              Alternate approver
            </span>
            <select
              aria-label="Alternate approver"
              value={alternateId}
              onChange={(event) => setAlternateId(event.target.value)}
              className="w-full rounded-xl border border-slate-200 px-3 py-2"
              required
            >
              <option value="">Select alternate</option>
              {(setup?.governance_candidates || []).map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.full_name}
                  {candidate.job_title ? ` — ${candidate.job_title}` : ''}
                </option>
              ))}
            </select>
          </label>

          <div className="md:col-span-2">
            <Button
              type="submit"
              disabled={
                loading
                || !ownerId
                || !alternateId
                || ownerId === alternateId
              }
            >
              Save approval governance
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <Sparkles className="mt-1 text-blue-600" size={22} />
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
                Standard policy pack
              </p>
              <h3 className="mt-1 text-lg font-bold text-slate-950">
                Configure entitlement formulas
              </h3>
              <p className="mt-1 text-sm text-slate-600">
                Edit the defaults before activation. Future accrual runs use
                the stored method and annual entitlement.
              </p>
            </div>
          </div>
          <Badge tone="blue">
            {policies.length} categories
          </Badge>
        </div>

        <div className="mt-5 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500">
                <th className="px-3 py-2">Category</th>
                <th className="px-3 py-2">Days</th>
                <th className="px-3 py-2">Allocation</th>
                <th className="px-3 py-2">Pay %</th>
                <th className="px-3 py-2">Carryover expiry</th>
              </tr>
            </thead>
            <tbody>
              {policies.map((policy, index) => (
                <tr key={policy.code} className="border-b border-slate-100">
                  <td className="px-3 py-3">
                    <input
                      aria-label={`${policy.code} name`}
                      value={policy.name}
                      onChange={(event) => updatePolicy(
                        index,
                        'name',
                        event.target.value,
                      )}
                      className="min-w-52 rounded-lg border border-slate-200 px-2 py-1.5"
                    />
                  </td>
                  <td className="px-3 py-3">
                    <input
                      aria-label={`${policy.code} entitlement`}
                      type="number"
                      min="0"
                      step="0.25"
                      value={policy.annual_entitlement_days}
                      onChange={(event) => updatePolicy(
                        index,
                        'annual_entitlement_days',
                        event.target.value,
                      )}
                      className="w-24 rounded-lg border border-slate-200 px-2 py-1.5"
                    />
                  </td>
                  <td className="px-3 py-3">
                    <select
                      aria-label={`${policy.code} allocation`}
                      value={policy.entitlement_mode}
                      onChange={(event) => updatePolicy(
                        index,
                        'entitlement_mode',
                        event.target.value,
                      )}
                      className="rounded-lg border border-slate-200 px-2 py-1.5"
                    >
                      <option value="accrued">Accrued monthly</option>
                      <option value="granted_upfront">Granted upfront</option>
                      <option value="event_based">Event based</option>
                      <option value="unlimited">Unlimited</option>
                      <option value="manual">Manual</option>
                    </select>
                  </td>
                  <td className="px-3 py-3">
                    <input
                      aria-label={`${policy.code} pay percentage`}
                      type="number"
                      min="0"
                      max="100"
                      value={policy.pay_percentage}
                      onChange={(event) => updatePolicy(
                        index,
                        'pay_percentage',
                        event.target.value,
                      )}
                      className="w-20 rounded-lg border border-slate-200 px-2 py-1.5"
                    />
                  </td>
                  <td className="px-3 py-3">
                    <input
                      aria-label={`${policy.code} carryover expiry months`}
                      type="number"
                      min="0"
                      max="24"
                      value={policy.carryover_expiry_months}
                      onChange={(event) => updatePolicy(
                        index,
                        'carryover_expiry_months',
                        event.target.value,
                      )}
                      className="w-24 rounded-lg border border-slate-200 px-2 py-1.5"
                      placeholder="None"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <Button onClick={applyPack} disabled={loading}>
            Apply pack and initialize balances
          </Button>
          <Button
            variant="secondary"
            onClick={() => onInitializeBalances({})}
            disabled={loading}
          >
            <RefreshCcw size={16} />
            Re-run opening balances
          </Button>
          <Button
            variant="secondary"
            onClick={() => onRunAccruals({})}
            disabled={loading}
          >
            Run scheduled allocations
          </Button>
        </div>
      </Card>
    </div>
  );
}
