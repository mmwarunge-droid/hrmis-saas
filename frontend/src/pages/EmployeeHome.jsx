import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BookOpenCheck,
  Bot,
  Cake,
  CalendarDays,
  CalendarHeart,
  FileText,
  MapPin,
  Pencil,
  Plane,
  Sparkles,
  UserPlus,
  UsersRound,
} from 'lucide-react';
import { Link } from 'react-router-dom';

import { employeeHomeApi } from '../api/employeeHomeApi.js';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Input from '../components/ui/Input.jsx';
import Modal from '../components/ui/Modal.jsx';

const SECTION_LABELS = {
  birthdays: 'Birthdays',
  essentials: 'Essentials',
  people_out_today: 'People out today',
  events_this_week: 'Events this week',
  new_hires: 'New hires',
  anniversaries: 'Anniversaries',
  our_people: 'Our people',
};

function formatDate(value, options = { day: 'numeric', month: 'short' }) {
  if (!value) return 'Date not set';
  return new Intl.DateTimeFormat('en', options).format(new Date(`${value}T00:00:00`));
}

function formatDateTime(value) {
  if (!value) return 'Time not set';
  return new Intl.DateTimeFormat('en', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
}

function PersonAvatar({ person, size = 'md' }) {
  if (person.profile_photo_url) {
    const sizes = { sm: 'h-9 w-9', md: 'h-11 w-11', lg: 'h-16 w-16' };
    return (
      <img
        src={person.profile_photo_url}
        alt=""
        className={`${sizes[size]} rounded-2xl object-cover ring-1 ring-slate-200`}
      />
    );
  }
  return <Avatar name={person.full_name} size={size} />;
}

function PersonLink({ person, detail, badge }) {
  return (
    <Link
      to={`/employees/${person.id}`}
      className="group flex items-center gap-3 rounded-2xl border border-slate-100 bg-slate-50/70 p-3 transition hover:-translate-y-0.5 hover:border-cyan-200 hover:bg-cyan-50/40"
    >
      <PersonAvatar person={person} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-slate-950 group-hover:text-cyan-800">
          {person.full_name}
        </span>
        <span className="mt-0.5 block truncate text-xs text-slate-500">{detail}</span>
      </span>
      {badge}
      <ArrowRight size={15} className="shrink-0 text-slate-300 group-hover:text-cyan-700" />
    </Link>
  );
}

function SectionCard({ icon: Icon, eyebrow, title, action, children, id }) {
  return (
    <Card id={id} className="h-full">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-cyan-50 text-cyan-700">
            <Icon size={19} />
          </span>
          <div>
            {eyebrow && (
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-700">
                {eyebrow}
              </p>
            )}
            <h2 className="text-lg font-bold text-slate-950">{title}</h2>
          </div>
        </div>
        {action}
      </div>
      <div className="mt-5">{children}</div>
    </Card>
  );
}

function EmptyMessage({ children }) {
  return (
    <p className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-500">
      {children}
    </p>
  );
}

function ProfileForm({ viewer, onSave, loading }) {
  const [form, setForm] = useState({
    date_of_birth: viewer.date_of_birth || '',
    birthday_visibility: viewer.birthday_visibility || 'colleagues',
    biography: viewer.biography || '',
    hobbies: (viewer.hobbies || []).join(', '),
    profile_photo_url: viewer.profile_photo_url || '',
    profile_cover_url: viewer.profile_cover_url || '',
    gender_identity: viewer.gender_identity || 'prefer_not_to_say',
    gender_self_description: viewer.gender_self_description || '',
  });

  const change = (key) => (event) => {
    setForm((current) => ({ ...current, [key]: event.target.value }));
  };

  const submit = (event) => {
    event.preventDefault();
    onSave({
      date_of_birth: form.date_of_birth || null,
      birthday_visibility: form.birthday_visibility,
      biography: form.biography.trim() || null,
      hobbies: form.hobbies
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
      profile_photo_url: form.profile_photo_url.trim() || null,
      profile_cover_url: form.profile_cover_url.trim() || null,
      gender_identity: form.gender_identity || null,
      gender_self_description: form.gender_identity === 'self_described'
        ? form.gender_self_description.trim() || null
        : null,
    });
  };

  return (
    <form className="space-y-5" onSubmit={submit}>
      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label="Date of birth"
          type="date"
          value={form.date_of_birth}
          onChange={change('date_of_birth')}
        />
        <label className="block space-y-1">
          <span className="text-sm font-medium text-slate-700">Birthday visibility</span>
          <select
            value={form.birthday_visibility}
            onChange={change('birthday_visibility')}
            className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          >
            <option value="colleagues">Show day and month to colleagues</option>
            <option value="hr_only">HR only</option>
            <option value="hidden">Hidden</option>
          </select>
        </label>
        <Input
          label="Profile photo URL"
          type="url"
          value={form.profile_photo_url}
          onChange={change('profile_photo_url')}
          placeholder="https://…"
        />
        <Input
          label="Profile cover URL"
          type="url"
          value={form.profile_cover_url}
          onChange={change('profile_cover_url')}
          placeholder="https://…"
        />
        <label className="block space-y-1">
          <span className="text-sm font-medium text-slate-700">Gender</span>
          <select
            value={form.gender_identity}
            onChange={change('gender_identity')}
            className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          >
            <option value="prefer_not_to_say">Prefer not to say</option>
            <option value="woman">Woman</option>
            <option value="man">Man</option>
            <option value="non_binary">Non-binary</option>
            <option value="self_described">Self-described</option>
          </select>
        </label>
        {form.gender_identity === 'self_described' && (
          <Input
            label="How you describe your gender"
            value={form.gender_self_description}
            onChange={change('gender_self_description')}
          />
        )}
      </div>
      <label className="block space-y-1">
        <span className="text-sm font-medium text-slate-700">About me</span>
        <textarea
          value={form.biography}
          onChange={change('biography')}
          rows={4}
          maxLength={2000}
          className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder="Share a short introduction colleagues can see."
        />
      </label>
      <Input
        label="Hobbies and interests"
        value={form.hobbies}
        onChange={change('hobbies')}
        placeholder="Hiking, football, music"
      />
      <p className="text-xs leading-5 text-slate-500">
        Colleagues never see your birth year. Gender and hobbies appear only in privacy-protected organization totals.
      </p>
      <div className="flex justify-end">
        <Button type="submit" variant="accent" disabled={loading}>
          {loading ? 'Saving…' : 'Save profile'}
        </Button>
      </div>
    </form>
  );
}

export default function EmployeeHome() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [profileOpen, setProfileOpen] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    let active = true;
    employeeHomeApi.get()
      .then((response) => {
        if (active) setData(response.data);
      })
      .catch((err) => {
        if (active) setError(err.error?.message || 'Unable to load your employee home.');
      });
    return () => { active = false; };
  }, []);

  const enabled = useMemo(
    () => new Set(data?.enabled_sections || []),
    [data?.enabled_sections],
  );
  const order = data?.section_order || [];

  const saveProfile = async (payload) => {
    setSavingProfile(true);
    setError('');
    try {
      const response = await employeeHomeApi.updateProfile(payload);
      setData((current) => ({ ...current, viewer: response.data }));
      setProfileOpen(false);
      setMessage('Your employee profile was updated.');
    } catch (err) {
      setError(err.error?.message || 'Your profile could not be updated.');
    } finally {
      setSavingProfile(false);
    }
  };

  if (error && !data) return <Alert type="error">{error}</Alert>;
  if (!data) {
    return <div className="h-[38rem] animate-pulse rounded-[2rem] bg-slate-100" />;
  }

  const { branding, viewer } = data;
  const firstName = viewer.preferred_name || viewer.first_name || viewer.full_name?.split(' ')[0] || 'there';
  const quickActions = [
    { to: '/leave', label: 'Request time off', detail: 'Submit and track leave', icon: Plane },
    { to: '/ask-ace', label: 'Ask a question', detail: 'Find help from approved resources', icon: Bot },
    { to: '#essentials', label: 'Essentials', detail: 'Policies and training', icon: BookOpenCheck },
    { to: '/employees', label: 'People directory', detail: 'Find a colleague', icon: UsersRound },
  ];

  const sectionRenderers = {
    birthdays: () => (
      <SectionCard icon={Cake} eyebrow="Celebrate" title="Birthdays">
        <div className="space-y-2">
          {data.birthdays.length ? data.birthdays.map((person) => (
            <PersonLink
              key={person.id}
              person={person}
              detail={person.is_today ? 'Birthday today' : formatDate(person.date)}
              badge={person.is_today ? <Badge tone="violet">Today</Badge> : null}
            />
          )) : <EmptyMessage>No colleague birthdays in the next 30 days.</EmptyMessage>}
        </div>
      </SectionCard>
    ),
    essentials: () => (
      <SectionCard icon={FileText} eyebrow="Recommended" title="Essentials" id="essentials">
        <div className="space-y-2">
          {data.essentials.length ? data.essentials.map((item) => (
            <a
              key={item.id}
              href={item.download_url}
              className="group flex items-center gap-3 rounded-2xl border border-slate-100 bg-slate-50/70 p-3 transition hover:border-cyan-200 hover:bg-cyan-50/40"
            >
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-white text-cyan-700 shadow-sm">
                <FileText size={18} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-slate-950">{item.title}</span>
                <span className="mt-0.5 block text-xs capitalize text-slate-500">
                  {item.document_type || 'Document'}
                </span>
              </span>
              <Badge tone={item.importance === 'required' ? 'amber' : 'blue'}>
                {item.importance}
              </Badge>
            </a>
          )) : <EmptyMessage>Your organization has not published any essentials yet.</EmptyMessage>}
        </div>
      </SectionCard>
    ),
    people_out_today: () => (
      <SectionCard icon={CalendarDays} eyebrow="Availability" title="People out today">
        <div className="space-y-2">
          {data.people_out_today.length ? data.people_out_today.map((person) => (
            <PersonLink
              key={person.id}
              person={person}
              detail={`Expected back ${formatDate(person.expected_return_date)}`}
              badge={<Badge tone="amber">Out today</Badge>}
            />
          )) : <EmptyMessage>Everyone currently appears available today.</EmptyMessage>}
        </div>
      </SectionCard>
    ),
    events_this_week: () => (
      <SectionCard icon={CalendarHeart} eyebrow="This week" title="Events">
        <div className="space-y-3">
          {data.events_this_week.length ? data.events_this_week.map((event) => (
            <Link
              key={event.id}
              to={`/events/${event.id}`}
              className="group block overflow-hidden rounded-2xl border border-slate-100 bg-slate-50/70 transition hover:-translate-y-0.5 hover:border-cyan-200"
            >
              {event.image_url && (
                <img src={event.image_url} alt="" className="h-24 w-full object-cover" />
              )}
              <div className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-950 group-hover:text-cyan-800">{event.title}</p>
                    <p className="mt-1 text-xs text-slate-500">{formatDateTime(event.starts_at)}</p>
                  </div>
                  <ArrowRight size={16} className="text-slate-300 group-hover:text-cyan-700" />
                </div>
                {event.location && (
                  <p className="mt-3 flex items-center gap-1.5 text-xs text-slate-500">
                    <MapPin size={13} /> {event.location}
                  </p>
                )}
              </div>
            </Link>
          )) : <EmptyMessage>No organization events are published for this week.</EmptyMessage>}
        </div>
      </SectionCard>
    ),
    new_hires: () => (
      <SectionCard icon={UserPlus} eyebrow="Welcome" title="New hires">
        <div className="space-y-2">
          {data.new_hires.length ? data.new_hires.map((person) => (
            <PersonLink
              key={person.id}
              person={person}
              detail={`${person.job_title || 'New colleague'} · Joined ${formatDate(person.hire_date)}`}
              badge={<Badge tone="green">New</Badge>}
            />
          )) : <EmptyMessage>No new colleagues joined within the configured window.</EmptyMessage>}
        </div>
      </SectionCard>
    ),
    anniversaries: () => (
      <SectionCard icon={CalendarHeart} eyebrow="Milestones" title="Anniversaries">
        <div className="space-y-2">
          {data.anniversaries.length ? data.anniversaries.map((person) => (
            <PersonLink
              key={person.id}
              person={person}
              detail={`${person.years} year${person.years === 1 ? '' : 's'} · ${formatDate(person.date)}`}
              badge={person.is_today ? <Badge tone="violet">Today</Badge> : null}
            />
          )) : <EmptyMessage>No service anniversaries in the next 30 days.</EmptyMessage>}
        </div>
      </SectionCard>
    ),
    our_people: () => (
      <SectionCard icon={UsersRound} eyebrow="Organization" title="Our people">
        {!data.people_statistics ? (
          <EmptyMessage>Organization people insights are disabled.</EmptyMessage>
        ) : (
          <div className="space-y-5">
            <div className="rounded-2xl bg-slate-950 p-5 text-white">
              <p className="text-3xl font-bold">{data.people_statistics.total_employees}</p>
              <p className="mt-1 text-sm text-slate-300">Active colleagues</p>
            </div>
            {[
              ['Locations', data.people_statistics.locations],
              ['Departments', data.people_statistics.departments],
              ['Gender', data.people_statistics.gender],
              ['Popular interests', data.people_statistics.hobbies],
            ].map(([label, items]) => items?.length ? (
              <div key={label}>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">{label}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {items.slice(0, 6).map((item) => (
                    <Badge key={`${label}-${item.key}`} tone="cyan">
                      {item.label} · {item.count}
                    </Badge>
                  ))}
                </div>
              </div>
            ) : null)}
            <p className="text-xs leading-5 text-slate-500">
              Small groups are omitted to protect colleague privacy.
            </p>
          </div>
        )}
      </SectionCard>
    ),
  };

  return (
    <div className="space-y-6 pb-10">
      {error && <Alert type="error">{error}</Alert>}
      {message && <Alert type="success">{message}</Alert>}

      <section
        className="relative min-h-[19rem] overflow-hidden rounded-[2rem] bg-gradient-to-br from-slate-950 via-blue-950 to-cyan-900 p-6 text-white shadow-xl md:p-9"
        style={branding.banner_url ? {
          backgroundImage: `linear-gradient(110deg, rgba(2,6,23,.93), rgba(8,47,73,.65)), url(${branding.banner_url})`,
          backgroundPosition: 'center',
          backgroundSize: 'cover',
        } : undefined}
      >
        <div className="absolute -right-16 -top-20 h-72 w-72 rounded-full bg-cyan-300/20 blur-3xl" />
        <div className="relative flex h-full flex-col justify-between gap-12">
          <div className="flex items-start justify-between gap-5">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-cyan-200">
                {branding.organization_name}
              </p>
              <h1 className="mt-4 max-w-3xl text-3xl font-bold tracking-tight md:text-5xl">
                Hi {firstName}, glad you’re here <span aria-hidden="true">👋</span>
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-200 md:text-base">
                {branding.welcome_message || 'Everything you need to stay connected and get work done.'}
              </p>
            </div>
            {branding.logo_url ? (
              <img
                src={branding.logo_url}
                alt={`${branding.organization_name} logo`}
                className="h-16 w-16 rounded-2xl bg-white object-contain p-2 shadow-xl md:h-20 md:w-20"
              />
            ) : (
              <span className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-white/10 text-2xl font-bold ring-1 ring-white/20 md:h-20 md:w-20">
                {branding.organization_name?.slice(0, 1)}
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-white/10 bg-white/10 p-4 backdrop-blur-md">
            <div className="flex items-center gap-3">
              <PersonAvatar person={viewer} size="lg" />
              <div>
                <p className="font-bold">{viewer.full_name}</p>
                <p className="text-sm text-slate-200">{viewer.job_title || 'Employee'}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {viewer.id && (
                <Link to="/profile">
                  <Button variant="secondary" size="sm">View my profile</Button>
                </Link>
              )}
              {viewer.id && (
                <Button
                  variant="accent"
                  size="sm"
                  onClick={() => setProfileOpen(true)}
                >
                  <Pencil size={15} /> Complete profile
                </Button>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {quickActions.map(({ to, label, detail, icon: Icon }) => {
          const content = (
            <Card className="group h-full transition hover:-translate-y-1 hover:border-cyan-200">
              <span className="grid h-11 w-11 place-items-center rounded-2xl bg-cyan-50 text-cyan-700 group-hover:bg-cyan-100">
                <Icon size={20} />
              </span>
              <div className="mt-4 flex items-end justify-between gap-3">
                <div>
                  <p className="font-bold text-slate-950">{label}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p>
                </div>
                <ArrowRight size={17} className="text-slate-300 group-hover:text-cyan-700" />
              </div>
            </Card>
          );
          if (to.startsWith('#')) return <a key={label} href={to}>{content}</a>;
          return <Link key={label} to={to}>{content}</Link>;
        })}
      </section>

      <Card className="overflow-hidden bg-gradient-to-r from-violet-50 via-white to-cyan-50">
        <div className="flex flex-wrap items-center justify-between gap-5">
          <div className="flex items-center gap-4">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-violet-600 text-white shadow-lg shadow-violet-200">
              <Bot size={22} />
            </span>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-violet-700">Ask ACE</p>
              <h2 className="mt-1 text-xl font-bold text-slate-950">Have a workplace question?</h2>
              <p className="mt-1 text-sm text-slate-600">
                Use your organization’s approved employee help experience.
              </p>
            </div>
          </div>
          <Link to="/ask-ace">
            <Button variant="accent">
              <Sparkles size={17} /> Ask a question
            </Button>
          </Link>
        </div>
      </Card>

      <section className="grid gap-6 xl:grid-cols-2">
        {order
          .filter((section) => enabled.has(section) && sectionRenderers[section])
          .map((section) => (
            <div key={section} aria-label={SECTION_LABELS[section]}>
              {sectionRenderers[section]()}
            </div>
          ))}
      </section>

      <Modal
        title="Complete your employee profile"
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
        size="xl"
      >
        <ProfileForm viewer={viewer} onSave={saveProfile} loading={savingProfile} />
      </Modal>
    </div>
  );
}
