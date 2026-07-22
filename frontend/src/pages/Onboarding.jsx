import { useEffect, useState } from 'react';
import { onboardingApi } from '../api/onboardingApi';
import OnboardingChecklist from '../components/onboarding/OnboardingChecklist.jsx';
import Alert from '../components/ui/Alert.jsx';

export default function Onboarding() {
  const [tasks, setTasks] = useState([]);
  const [error, setError] = useState('');
  const load = () => onboardingApi.myTasks().then((res) => setTasks(res.data.items)).catch((err) => setError(err.error?.message || 'Load failed'));
  useEffect(() => { load(); }, []);
  return <div className="space-y-6"><div><h1 className="text-2xl font-bold">Onboarding</h1><p className="text-slate-500">New hire task checklist.</p></div>{error && <Alert type="error">{error}</Alert>}<OnboardingChecklist tasks={tasks} onComplete={(id) => onboardingApi.complete(id).then(load)} /></div>;
}
