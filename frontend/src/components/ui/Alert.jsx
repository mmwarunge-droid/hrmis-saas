import { AlertCircle, CheckCircle2, Info } from 'lucide-react';

export default function Alert({ children, type = 'info' }) {
  const styles = {
    error: 'border-red-200 bg-red-50 text-red-700',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    info: 'border-cyan-200 bg-cyan-50 text-cyan-800',
  };
  const Icon = type === 'error' ? AlertCircle : type === 'success' ? CheckCircle2 : Info;
  return <div className={`flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm ${styles[type]}`}><Icon className="mt-0.5 shrink-0" size={17} /><div>{children}</div></div>;
}
