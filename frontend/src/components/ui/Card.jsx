export default function Card({ children, className = '', padded = true, as: Component = 'section' }) {
  return (
    <Component
      className={`rounded-xl border border-slate-200 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04),0_8px_24px_rgba(15,23,42,0.035)] ${padded ? 'p-5 md:p-6' : ''} ${className}`}
    >
      {children}
    </Component>
  );
}
