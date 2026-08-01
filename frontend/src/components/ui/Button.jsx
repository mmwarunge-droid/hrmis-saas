export default function Button({
  children,
  className = '',
  variant = 'primary',
  size = 'md',
  type,
  ...props
}) {
  const variants = {
    primary: 'border border-blue-700 bg-blue-700 text-white shadow-sm hover:border-blue-800 hover:bg-blue-800 focus-visible:ring-blue-200',
    accent: 'border border-blue-700 bg-blue-700 text-white shadow-sm hover:border-blue-800 hover:bg-blue-800 focus-visible:ring-blue-200',
    secondary: 'border border-slate-300 bg-white text-slate-800 shadow-sm hover:border-slate-400 hover:bg-slate-50 focus-visible:ring-blue-100',
    soft: 'border border-blue-100 bg-blue-50 text-blue-800 hover:border-blue-200 hover:bg-blue-100 focus-visible:ring-blue-100',
    danger: 'border border-red-600 bg-red-600 text-white shadow-sm hover:border-red-700 hover:bg-red-700 focus-visible:ring-red-200',
    ghost: 'border border-transparent bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-950 focus-visible:ring-slate-200',
  };
  const sizes = {
    xs: 'min-h-7 rounded-md px-2 py-1 text-[11px]',
    sm: 'min-h-8 rounded-lg px-3 py-1.5 text-xs',
    md: 'min-h-10 rounded-lg px-4 py-2 text-sm',
    lg: 'min-h-11 rounded-[10px] px-5 py-2.5 text-sm',
  };

  return (
    <button
      type={type}
      className={`inline-flex shrink-0 items-center justify-center gap-2 font-semibold leading-none transition duration-150 focus:outline-none focus-visible:ring-4 disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant] || variants.primary} ${sizes[size] || sizes.md} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
