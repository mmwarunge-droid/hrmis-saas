import Card from '../ui/Card.jsx';
import './ProfileHeader.css';

/** Only the avatar crosses the cover boundary; identity/actions stay in flow. */
export default function ProfileHeader({
  coverClassName = '', coverStyle, avatar, avatarSize = '5rem',
  name, status, subtitle, eyebrow, actions, tabs,
}) {
  return (
    <Card padded={false} className="profile-header min-w-0 overflow-hidden">
      <div data-profile-cover aria-hidden="true" className={`h-32 md:h-40 ${coverClassName}`} style={coverStyle} />
      <div data-profile-body className="grid min-w-0 grid-cols-1 gap-x-5 gap-y-4 px-5 pb-5 sm:grid-cols-[auto_minmax(0,1fr)] md:px-6 xl:grid-cols-[auto_minmax(0,1fr)_minmax(0,auto)]">
        <div data-profile-avatar className="relative w-fit self-start" style={{ marginTop: `calc(${avatarSize} / -2)` }}>
          {avatar}
        </div>
        <div data-profile-identity className="min-w-0 pt-4 [overflow-wrap:anywhere]">
          {eyebrow && <p className="mb-1 text-xs font-bold uppercase tracking-[0.18em] text-blue-700">{eyebrow}</p>}
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="min-w-0 text-2xl font-bold tracking-[-0.025em] text-slate-950">{name}</h1>
            {status}
          </div>
          <p className="mt-1 text-sm font-medium text-slate-600">{subtitle}</p>
        </div>
        {actions && <div data-profile-actions className="flex min-w-0 flex-wrap items-start gap-2 sm:col-start-2 xl:col-start-3 xl:pt-4">{actions}</div>}
      </div>
      {tabs && <div data-profile-tabs className="min-w-0 px-5 md:px-6">{tabs}</div>}
    </Card>
  );
}
