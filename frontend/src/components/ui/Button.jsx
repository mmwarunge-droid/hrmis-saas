export default function Button({ children, className = '', variant = 'primary', size = 'md', ...props }) {
  const variants = {
    primary: 'bg-slate-950 text-white shadow-sm hover:bg-slate-800 focus:ring-slate-300',
    accent: 'bg-gradient-to-r from-cyan-600 to-blue-700 text-white shadow-lg shadow-cyan-950/10 hover:from-cyan-500 hover:to-blue-600 focus:ring-cyan-200',
    secondary: 'border border-slate-200 bg-white text-slate-800 shadow-sm hover:bg-slate-50 focus:ring-slate-200',
    soft: 'bg-cyan-50 text-cyan-800 hover:bg-cyan-100 focus:ring-cyan-100',
    danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-200',
    ghost: 'bg-transparent text-slate-600 hover:bg-slate-100 focus:ring-slate-200',
  };
  const sizes = {
    sm: 'rounded-xl px-3 py-1.5 text-xs',
    md: 'rounded-2xl px-4 py-2.5 text-sm',
    lg: 'rounded-2xl px-5 py-3 text-sm',
  };
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 font-semibold transition focus:outline-none focus:ring-4 disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
