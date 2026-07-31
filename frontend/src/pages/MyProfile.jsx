import { useEffect, useState } from 'react';
import {
  Camera,
  ExternalLink,
  ImagePlus,
  Save,
  UserRound,
} from 'lucide-react';
import { Link } from 'react-router-dom';

import { employeeHomeApi } from '../api/employeeHomeApi.js';
import Alert from '../components/ui/Alert.jsx';
import Avatar from '../components/ui/Avatar.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Input from '../components/ui/Input.jsx';

function personImage(viewer, size = 'h-28 w-28') {
  if (viewer.profile_photo_url) {
    return (
      <img
        src={viewer.profile_photo_url}
        alt={`${viewer.full_name} profile`}
        className={`${size} rounded-[2rem] border-4 border-white object-cover shadow-xl`}
      />
    );
  }
  return (
    <span className="grid h-28 w-28 place-items-center rounded-[2rem] border-4 border-white bg-white shadow-xl">
      <Avatar name={viewer.full_name} size="lg" />
    </span>
  );
}

function initialForm(viewer) {
  return {
    preferred_name: viewer.preferred_name || '',
    phone: viewer.phone || '',
    date_of_birth: viewer.date_of_birth || '',
    birthday_visibility: viewer.birthday_visibility || 'colleagues',
    biography: viewer.biography || '',
    hobbies: (viewer.hobbies || []).join(', '),
    gender_identity: viewer.gender_identity || 'prefer_not_to_say',
    gender_self_description: viewer.gender_self_description || '',
  };
}

export default function MyProfile() {
  const [branding, setBranding] = useState(null);
  const [viewer, setViewer] = useState(null);
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    let active = true;
    employeeHomeApi.get()
      .then((response) => {
        if (!active) return;
        if (!response.data.viewer?.id) {
          setError('Your account is not linked to an employee profile.');
          return;
        }
        setBranding(response.data.branding);
        setViewer(response.data.viewer);
        setForm(initialForm(response.data.viewer));
      })
      .catch((err) => {
        if (active) setError(err.error?.message || 'Unable to load your profile.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const change = (key) => (event) => {
    setForm((current) => ({ ...current, [key]: event.target.value }));
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const payload = {
        preferred_name: form.preferred_name.trim() || null,
        phone: form.phone.trim() || null,
        date_of_birth: form.date_of_birth || null,
        birthday_visibility: form.birthday_visibility,
        biography: form.biography.trim() || null,
        hobbies: form.hobbies
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        gender_identity: form.gender_identity || null,
        gender_self_description: form.gender_identity === 'self_described'
          ? form.gender_self_description.trim() || null
          : null,
      };
      const response = await employeeHomeApi.updateProfile(payload);
      setViewer(response.data);
      setForm(initialForm(response.data));
      setMessage('Your profile has been updated.');
    } catch (err) {
      setError(err.error?.message || 'Your profile could not be updated.');
    } finally {
      setSaving(false);
    }
  };

  const upload = (asset) => async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setUploading(asset);
    setError('');
    setMessage('');
    try {
      const response = await employeeHomeApi.uploadProfileImage(asset, file);
      setViewer(response.data);
      setMessage(asset === 'photo'
        ? 'Your profile photo has been updated.'
        : 'Your profile cover has been updated.');
    } catch (err) {
      setError(err.error?.message || 'The image could not be uploaded.');
    } finally {
      setUploading('');
    }
  };

  if (loading) {
    return <div className="h-[38rem] animate-pulse rounded-[2rem] bg-slate-100" />;
  }
  if (!viewer || !form) return <Alert type="error">{error}</Alert>;

  const cover = viewer.profile_cover_url || branding?.banner_url;

  return (
    <div className="space-y-6 pb-10">
      {error && <Alert type="error">{error}</Alert>}
      {message && <Alert type="success">{message}</Alert>}

      <Card padded={false} className="overflow-hidden">
        <div
          className="relative h-52 bg-gradient-to-br from-slate-950 via-blue-950 to-cyan-800"
          style={cover ? {
            backgroundImage: `linear-gradient(110deg, rgba(2,6,23,.72), rgba(8,47,73,.32)), url(${cover})`,
            backgroundPosition: 'center',
            backgroundSize: 'cover',
          } : undefined}
        >
          <label className="absolute right-5 top-5 cursor-pointer rounded-2xl border border-white/20 bg-slate-950/60 px-4 py-2 text-sm font-semibold text-white backdrop-blur transition hover:bg-slate-950/80">
            <input
              aria-label="Upload profile cover"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="sr-only"
              disabled={Boolean(uploading)}
              onChange={upload('cover')}
            />
            <span className="flex items-center gap-2">
              <ImagePlus size={16} />
              {uploading === 'cover' ? 'Uploading…' : 'Change cover'}
            </span>
          </label>
        </div>

        <div className="relative px-6 pb-6 md:px-8">
          <div className="-mt-14 flex flex-wrap items-end justify-between gap-5">
            <div className="flex flex-wrap items-end gap-5">
              <div className="relative">
                {personImage(viewer)}
                <label className="absolute -bottom-2 -right-2 grid h-10 w-10 cursor-pointer place-items-center rounded-2xl bg-cyan-700 text-white shadow-lg transition hover:bg-cyan-600">
                  <input
                    aria-label="Upload profile photo"
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    className="sr-only"
                    disabled={Boolean(uploading)}
                    onChange={upload('photo')}
                  />
                  <Camera size={17} />
                </label>
              </div>
              <div className="pb-1">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-700">
                  My profile
                </p>
                <h1 className="mt-1 text-3xl font-bold text-slate-950">{viewer.full_name}</h1>
                <p className="mt-1 text-sm text-slate-500">
                  {viewer.job_title || 'Employee'}
                  {viewer.department_name ? ` · ${viewer.department_name}` : ''}
                </p>
              </div>
            </div>
            <Link to={`/employees/${viewer.id}`}>
              <Button variant="secondary">
                <ExternalLink size={16} /> View public profile
              </Button>
            </Link>
          </div>
        </div>
      </Card>

      <form onSubmit={save} className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-cyan-50 text-cyan-700">
              <UserRound size={20} />
            </span>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.17em] text-cyan-700">
                Personal details
              </p>
              <h2 className="text-xl font-bold text-slate-950">How colleagues know you</h2>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <Input
              label="Preferred name"
              value={form.preferred_name}
              onChange={change('preferred_name')}
              maxLength={120}
              placeholder={viewer.first_name || 'Preferred name'}
            />
            <Input
              label="Work phone"
              value={form.phone}
              onChange={change('phone')}
              maxLength={40}
              placeholder="+254…"
            />
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
                maxLength={120}
              />
            )}
          </div>

          <label className="mt-4 block space-y-1">
            <span className="text-sm font-medium text-slate-700">About me</span>
            <textarea
              value={form.biography}
              onChange={change('biography')}
              rows={5}
              maxLength={2000}
              className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
              placeholder="Share a short introduction colleagues can see."
            />
          </label>

          <div className="mt-4">
            <Input
              label="Hobbies and interests"
              value={form.hobbies}
              onChange={change('hobbies')}
              placeholder="Hiking, football, music"
            />
          </div>

          <div className="mt-6 flex justify-end">
            <Button type="submit" variant="accent" disabled={saving || Boolean(uploading)}>
              <Save size={16} /> {saving ? 'Saving…' : 'Save profile'}
            </Button>
          </div>
        </Card>

        <Card>
          <p className="text-xs font-bold uppercase tracking-[0.17em] text-violet-700">
            Work profile
          </p>
          <h2 className="mt-1 text-xl font-bold text-slate-950">Organization information</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            Contact HR or an administrator to change organization-managed information.
          </p>

          <dl className="mt-6 space-y-4">
            {[
              ['Work email', viewer.email || 'Not set'],
              ['Job title', viewer.job_title || 'Not set'],
              ['Department', viewer.department_name || 'Not assigned'],
              ['Work location', viewer.work_location || 'Not set'],
              ['Employee number', viewer.employee_number || 'Not set'],
            ].map(([label, value]) => (
              <div key={label} className="rounded-2xl bg-slate-50 p-4">
                <dt className="text-xs font-bold uppercase tracking-[0.12em] text-slate-400">
                  {label}
                </dt>
                <dd className="mt-1 text-sm font-semibold text-slate-900">{value}</dd>
              </div>
            ))}
          </dl>

          <p className="mt-6 rounded-2xl border border-cyan-100 bg-cyan-50 p-4 text-xs leading-5 text-cyan-900">
            Colleagues never see your birth year. Gender and hobbies are used only in privacy-protected organization totals.
          </p>
        </Card>
      </form>
    </div>
  );
}
