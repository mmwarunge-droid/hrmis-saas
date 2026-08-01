import { Sparkles } from 'lucide-react';

export default function KineticLogo({ compact = false, inverse = false, className = '' }) {
  return (
    <div className={`flex min-w-0 items-center gap-2.5 ${className}`} aria-label="Kinetic">
      <span
        className={`relative grid h-9 w-9 shrink-0 place-items-center overflow-hidden rounded-[10px] shadow-sm ${
          inverse
            ? 'bg-white text-blue-700'
            : 'bg-gradient-to-br from-blue-600 to-blue-800 text-white'
        }`}
        aria-hidden="true"
      >
        <span className="absolute -right-2 -top-2 h-5 w-5 rounded-full bg-white/20" />
        <Sparkles size={17} strokeWidth={2.2} />
      </span>
      {!compact && (
        <span className="min-w-0 leading-none">
          <span className={`block truncate text-[15px] font-extrabold tracking-[-0.02em] ${inverse ? 'text-white' : 'text-slate-950'}`}>
            Kinetic
          </span>
          <span className={`mt-1 block text-[9px] font-bold uppercase tracking-[0.18em] ${inverse ? 'text-blue-200' : 'text-slate-400'}`}>
            People platform
          </span>
        </span>
      )}
    </div>
  );
}
