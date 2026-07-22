export default function Button({ children, className = '', variant = 'primary', ...props }) {
  const variants = {
    primary: 'bg-slate-950 text-white hover:bg-slate-800',
    secondary: 'bg-white text-slate-900 border border-slate-200 hover:bg-slate-50',
    danger: 'bg-red-600 text-white hover:bg-red-700',
  };
  return <button className={`rounded-xl px-4 py-2 text-sm font-semibold disabled:opacity-60 ${variants[variant]} ${className}`} {...props}>{children}</button>;
}
