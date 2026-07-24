export default function Card({ children, className = '', padded = true }) {
  return (
    <section className={`rounded-3xl border border-slate-200/80 bg-white shadow-[0_18px_50px_-35px_rgba(15,23,42,0.55)] ${padded ? 'p-5 md:p-6' : ''} ${className}`}>
      {children}
    </section>
  );
}
