export default function PageHeader({ eyebrow, title, description, actions, children }) {
  return (
    <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-1.5 text-[11px] font-bold uppercase tracking-[0.16em] text-blue-700">{eyebrow}</p>
        )}
        <h1 className="text-2xl font-bold tracking-[-0.025em] text-slate-950 md:text-[28px]">{title}</h1>
        {description && <p className="mt-1.5 max-w-3xl text-sm leading-6 text-slate-600">{description}</p>}
        {children}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
