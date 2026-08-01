export default function Spinner({ size = 'md', label = 'Loading' }) {
  const sizes = { sm: 'h-5 w-5 border-2', md: 'h-8 w-8 border-[3px]', lg: 'h-11 w-11 border-4' };
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-slate-500">
      <span className={`${sizes[size] || sizes.md} animate-spin rounded-full border-blue-100 border-t-blue-700`} />
      <span className="sr-only">{label}</span>
    </span>
  );
}
