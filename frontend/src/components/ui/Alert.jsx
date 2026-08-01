import { AlertCircle, CheckCircle2, Info, TriangleAlert } from 'lucide-react';

export default function Alert({ children, type = 'info', title }) {
  const styles = {
    error: 'border-red-200 bg-red-50 text-red-800',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    warning: 'border-amber-200 bg-amber-50 text-amber-900',
    info: 'border-blue-200 bg-blue-50 text-blue-800',
  };
  const icons = {
    error: AlertCircle,
    success: CheckCircle2,
    warning: TriangleAlert,
    info: Info,
  };
  const Icon = icons[type] || Info;

  return (
    <div role={type === 'error' ? 'alert' : 'status'} className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${styles[type] || styles.info}`}>
      <Icon className="mt-0.5 shrink-0" size={17} />
      <div className="min-w-0 leading-6">
        {title && <p className="font-bold">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  );
}
