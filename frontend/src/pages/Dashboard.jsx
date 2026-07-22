import { useEffect, useState } from 'react';
import { dashboardApi } from '../api/dashboardApi';
import Alert from '../components/ui/Alert.jsx';
import Card from '../components/ui/Card.jsx';
import Spinner from '../components/ui/Spinner.jsx';

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    Promise.all([dashboardApi.summary(), dashboardApi.complianceAlerts()])
      .then(([s, a]) => { setSummary(s.data); setAlerts(a.data); })
      .catch((err) => setError(err.error?.message || 'Failed to load dashboard'));
  }, []);
  if (!summary && !error) return <Spinner />;
  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-bold">Dashboard</h1><p className="text-slate-500">Operational HR health and compliance indicators.</p></div>
      {error && <Alert type="error">{error}</Alert>}
      {summary && <div className="grid gap-4 md:grid-cols-3">{Object.entries(summary).map(([key, value]) => <Card key={key}><p className="text-sm capitalize text-slate-500">{key.replaceAll('_', ' ')}</p><p className="mt-2 text-3xl font-bold">{value}</p></Card>)}</div>}
      {alerts && <Card><h2 className="font-bold">Compliance alerts</h2><p className="mt-2 text-sm text-slate-600">Expiring documents: {alerts.expiring_documents?.length || 0}</p><p className="text-sm text-slate-600">Employees missing contracts: {alerts.employees_missing_contracts?.length || 0}</p></Card>}
    </div>
  );
}
