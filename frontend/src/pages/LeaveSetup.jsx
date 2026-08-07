import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, Settings2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { leaveApi } from '../api/leaveApi.js';
import LeaveSetupPanel from '../components/leave/LeaveSetupPanel.jsx';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import { useToast } from '../context/ToastContext.jsx';

export default function LeaveSetup() {
  const [setup, setSetup] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await leaveApi.setup();
      setSetup(response.data);
      setError('');
    } catch (err) {
      setError(err.error?.message || 'Unable to load time-off setup.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const run = async (action, message) => {
    setSaving(true);
    setError('');
    try {
      await action();
      toast.success(message);
      await load();
      return true;
    } catch (err) {
      setError(err.error?.message || 'The setup action could not be completed.');
      return false;
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Time-off administration"
        title="Time-off setup"
        description="Configure organization approval governance, policy formulas, opening balances and scheduled allocations. Personal eligibility remains visible on the Time off page."
        actions={(
          <Link to="/leave">
            <Button variant="secondary"><ArrowLeft size={16} /> Back to time off</Button>
          </Link>
        )}
      />

      {error && <Alert type="error">{error}</Alert>}

      {loading ? (
        <Card className="py-14 text-center text-sm text-slate-500">
          Loading time-off configuration…
        </Card>
      ) : setup?.can_configure ? (
        <LeaveSetupPanel
          setup={setup}
          onSaveGovernance={(payload) => run(
            () => leaveApi.saveGovernance(payload),
            'Approval governance updated.',
          )}
          onApplyPack={(payload) => run(
            () => leaveApi.applyStandardPack(payload),
            'Standard leave policy pack applied.',
          )}
          onInitializeBalances={(payload) => run(
            () => leaveApi.initializeBalances(payload),
            'Opening balances initialized.',
          )}
          onRunAccruals={(payload = {}) => run(
            () => leaveApi.runAccruals(payload),
            'Scheduled leave allocations processed.',
          )}
          loading={saving}
        />
      ) : (
        <EmptyState
          icon={Settings2}
          title="Administrator action required"
          description="Only an organization owner, HR consultant or client administrator can change time-off governance and policies."
        />
      )}
    </div>
  );
}
