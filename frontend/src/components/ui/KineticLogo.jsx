export default function KineticLogo({ compact = false, inverse = false, className = '' }) {
  return (
    <div className={`flex min-w-0 items-center gap-2.5 ${className}`} aria-label="Kinetic">
      <span
        className="grid h-10 w-10 shrink-0 place-items-center"
        aria-hidden="true"
      >
        <img
          src="/kinetic.png"
          alt=""
          className="h-10 w-10 object-contain"
        />
      </span>

      {!compact && (
        <span className="min-w-0 leading-none">
          <span
            className={`block truncate text-[15px] font-extrabold tracking-[-0.02em] ${
              inverse ? 'text-white' : 'text-slate-950'
            }`}
          >
            Kinetic
          </span>
          <span
            className={`mt-1 block text-[9px] font-bold uppercase tracking-[0.18em] ${
              inverse ? 'text-blue-200' : 'text-slate-600'
            }`}
          >
            People platform
          </span>
        </span>
      )}
    </div>
  );
}
