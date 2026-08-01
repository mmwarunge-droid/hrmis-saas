export default function Skeleton({ className = '', lines = 0 }) {
  if (lines > 0) {
    return (
      <div className={`space-y-2 ${className}`} aria-hidden="true">
        {Array.from({ length: lines }, (_, index) => (
          <div key={index} className={`h-3 animate-pulse rounded bg-slate-200 ${index === lines - 1 ? 'w-2/3' : 'w-full'}`} />
        ))}
      </div>
    );
  }
  return <div className={`animate-pulse rounded-lg bg-slate-200 ${className}`} aria-hidden="true" />;
}
