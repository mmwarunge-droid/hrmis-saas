import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowDown,
  ArrowUp,
  CalendarPlus,
  FilePlus2,
  Eye,
  Image,
  Pencil,
  Save,
  Settings2,
  Trash2,
} from 'lucide-react';
import { Link } from 'react-router-dom';

import { employeeHomeApi } from '../api/employeeHomeApi.js';
import Alert from '../components/ui/Alert.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Input from '../components/ui/Input.jsx';
import Modal from '../components/ui/Modal.jsx';
import useTenant from '../hooks/useTenant.js';

const SECTION_OPTIONS = [
  ['birthdays', 'Birthdays'],
  ['essentials', 'Essentials'],
  ['people_out_today', 'People out today'],
  ['events_this_week', 'Events this week'],
  ['new_hires', 'New hires'],
  ['anniversaries', 'Anniversaries'],
  ['our_people', 'Our people'],
];

const EMPTY_EVENT = {
  title: '',
  description: '',
  starts_at: '',
  ends_at: '',
  location: '',
  meeting_url: '',
  image_url: '',
  audience: 'all',
  status: 'draft',
};

function toLocalInput(value) {
  if (!value) return '';
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function toPayloadDate(value) {
  return value ? new Date(value).toISOString() : null;
}

export default function EmployeeExperienceSettings() {
  const { tenantId } = useTenant();
  const [settings, setSettings] = useState(null);
  const [events, setEvents] = useState([]);
  const [essentials, setEssentials] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const [brandingUpload, setBrandingUpload] = useState('');
  const [bannerFile, setBannerFile] = useState(null);
  const [logoFile, setLogoFile] = useState(null);
  const [eventOpen, setEventOpen] = useState(false);
  const [eventForm, setEventForm] = useState(EMPTY_EVENT);
  const [editingEventId, setEditingEventId] = useState(null);
  const [essentialForm, setEssentialForm] = useState({
    document_id: '',
    display_title: '',
    importance: 'recommended',
  });

  const load = useCallback(async () => {
    if (!tenantId) return;
    setError('');
    try {
      const [settingsResponse, eventResponse, essentialResponse, documentResponse] = await Promise.all([
        employeeHomeApi.settings(tenantId),
        employeeHomeApi.events(tenantId),
        employeeHomeApi.essentials(tenantId),
        employeeHomeApi.documentOptions(tenantId),
      ]);
      setSettings(settingsResponse.data);
      setEvents(eventResponse.data.items || []);
      setEssentials(essentialResponse.data.items || []);
      setDocuments(documentResponse.data.items || []);
    } catch (err) {
      setError(err.error?.message || 'Unable to load employee experience settings.');
    }
  }, [tenantId]);

  useEffect(() => { load(); }, [load]);

  const availableDocuments = useMemo(() => {
    const used = new Set(essentials.map((item) => item.document_id));
    return documents.filter((document) => !used.has(document.id));
  }, [documents, essentials]);

  const changeSetting = (key, value) => {
    setSettings((current) => ({ ...current, [key]: value }));
  };

  const saveSettings = async () => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const response = await employeeHomeApi.updateSettings(tenantId, {
        banner_url: settings.banner_url || null,
        logo_url: settings.logo_url || null,
        welcome_message: settings.welcome_message,
        enabled_sections: settings.enabled_sections,
        section_order: settings.section_order,
        new_hire_window_days: Number(settings.new_hire_window_days),
        birthday_visibility_enabled: settings.birthday_visibility_enabled,
        anniversaries_enabled: settings.anniversaries_enabled,
        people_statistics_enabled: settings.people_statistics_enabled,
        assistant_enabled: settings.assistant_enabled,
        assistant_url: settings.assistant_url || null,
      });
      setSettings(response.data);
      setMessage('Employee homepage settings saved.');
    } catch (err) {
      setError(err.error?.message || 'Employee homepage settings could not be saved.');
    } finally {
      setSaving(false);
    }
  };

  const uploadBranding = async (asset, file) => {
    if (!file) return;
    setBrandingUpload(asset);
    setError('');
    setMessage('');
    try {
      const response = await employeeHomeApi.uploadBranding(
        tenantId,
        asset,
        file,
      );
      setSettings(response.data);
      if (asset === 'banner') setBannerFile(null);
      else setLogoFile(null);
      setMessage(`${asset === 'banner' ? 'Company banner' : 'Company logo'} uploaded.`);
    } catch (err) {
      setError(err.error?.message || 'The branding image could not be uploaded.');
    } finally {
      setBrandingUpload('');
    }
  };

  const toggleSection = (section) => {
    const enabled = new Set(settings.enabled_sections);
    if (enabled.has(section)) enabled.delete(section);
    else enabled.add(section);
    changeSetting('enabled_sections', [...enabled]);
  };

  const moveSection = (section, direction) => {
    const order = [...settings.section_order];
    const index = order.indexOf(section);
    const next = index + direction;
    if (index < 0 || next < 0 || next >= order.length) return;
    [order[index], order[next]] = [order[next], order[index]];
    changeSetting('section_order', order);
  };

  const openNewEvent = () => {
    setEditingEventId(null);
    setEventForm(EMPTY_EVENT);
    setEventOpen(true);
  };

  const openEditEvent = (event) => {
    setEditingEventId(event.id);
    setEventForm({
      title: event.title || '',
      description: event.description || '',
      starts_at: toLocalInput(event.starts_at),
      ends_at: toLocalInput(event.ends_at),
      location: event.location || '',
      meeting_url: event.meeting_url || '',
      image_url: event.image_url || '',
      audience: event.audience || 'all',
      status: event.status || 'draft',
    });
    setEventOpen(true);
  };

  const saveEvent = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload = {
        title: eventForm.title,
        description: eventForm.description || null,
        starts_at: toPayloadDate(eventForm.starts_at),
        ends_at: toPayloadDate(eventForm.ends_at),
        location: eventForm.location || null,
        meeting_url: eventForm.meeting_url || null,
        image_url: eventForm.image_url || null,
        audience: eventForm.audience,
        status: eventForm.status,
      };
      if (editingEventId) {
        await employeeHomeApi.updateEvent(tenantId, editingEventId, payload);
      } else {
        await employeeHomeApi.createEvent(tenantId, payload);
      }
      setEventOpen(false);
      setMessage(editingEventId ? 'Organization event updated.' : 'Organization event created.');
      await load();
    } catch (err) {
      setError(err.error?.message || 'The organization event could not be saved.');
    } finally {
      setSaving(false);
    }
  };

  const removeEvent = async (id) => {
    if (!window.confirm('Delete this organization event?')) return;
    setError('');
    try {
      await employeeHomeApi.removeEvent(tenantId, id);
      setEvents((current) => current.filter((event) => event.id !== id));
      setMessage('Organization event deleted.');
    } catch (err) {
      setError(err.error?.message || 'The organization event could not be deleted.');
    }
  };

  const addEssential = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await employeeHomeApi.createEssential(tenantId, {
        document_id: essentialForm.document_id,
        display_title: essentialForm.display_title || null,
        importance: essentialForm.importance,
        display_order: essentials.length,
        is_published: true,
      });
      setEssentialForm({ document_id: '', display_title: '', importance: 'recommended' });
      setMessage('Employee essential added.');
      await load();
    } catch (err) {
      setError(err.error?.message || 'The employee essential could not be added.');
    } finally {
      setSaving(false);
    }
  };

  const updateEssential = async (item, payload) => {
    setError('');
    try {
      const response = await employeeHomeApi.updateEssential(tenantId, item.id, payload);
      setEssentials((current) => current.map((entry) => (
        entry.id === item.id ? response.data : entry
      )));
    } catch (err) {
      setError(err.error?.message || 'The employee essential could not be updated.');
    }
  };

  const removeEssential = async (id) => {
    if (!window.confirm('Remove this document from employee essentials?')) return;
    setError('');
    try {
      await employeeHomeApi.removeEssential(tenantId, id);
      setEssentials((current) => current.filter((item) => item.id !== id));
      setMessage('Employee essential removed.');
    } catch (err) {
      setError(err.error?.message || 'The employee essential could not be removed.');
    }
  };

  if (!tenantId) {
    return <Alert>Select an organization before configuring the employee experience.</Alert>;
  }
  if (!settings) {
    return error ? <Alert type="error">{error}</Alert> : (
      <div className="h-[36rem] animate-pulse rounded-[2rem] bg-slate-100" />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-700">Administration</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-950">Employee experience</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Configure the branded employee homepage, visible sections, Ask ACE handoff, events and essential documents.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/employee-home">
            <Button variant="secondary">
              <Eye size={17} /> Preview employee home
            </Button>
          </Link>
          <Button variant="accent" onClick={saveSettings} disabled={saving}>
            <Save size={17} /> {saving ? 'Saving…' : 'Save homepage'}
          </Button>
        </div>
      </div>

      {error && <Alert type="error">{error}</Alert>}
      {message && <Alert type="success">{message}</Alert>}

      <Card>
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-cyan-50 text-cyan-700"><Image size={19} /></span>
          <div>
            <h2 className="text-lg font-bold text-slate-950">Branding and welcome</h2>
            <p className="text-sm text-slate-500">Upload PNG, JPEG or WebP images up to 5 MB, or use an approved HTTPS image URL.</p>
          </div>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <label className="block text-sm font-medium text-slate-700" htmlFor="homepage-banner-upload">
              Upload company banner
            </label>
            <input
              id="homepage-banner-upload"
              className="mt-2 block w-full text-sm text-slate-600 file:mr-3 file:rounded-xl file:border-0 file:bg-white file:px-3 file:py-2 file:font-semibold file:text-slate-700"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(event) => setBannerFile(event.target.files?.[0] || null)}
            />
            <Button
              className="mt-3"
              size="sm"
              variant="secondary"
              disabled={!bannerFile || brandingUpload === 'banner'}
              onClick={() => uploadBranding('banner', bannerFile)}
            >
              <Image size={15} />
              {brandingUpload === 'banner' ? 'Uploading…' : 'Upload banner'}
            </Button>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <label className="block text-sm font-medium text-slate-700" htmlFor="homepage-logo-upload">
              Upload company logo
            </label>
            <input
              id="homepage-logo-upload"
              className="mt-2 block w-full text-sm text-slate-600 file:mr-3 file:rounded-xl file:border-0 file:bg-white file:px-3 file:py-2 file:font-semibold file:text-slate-700"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(event) => setLogoFile(event.target.files?.[0] || null)}
            />
            <Button
              className="mt-3"
              size="sm"
              variant="secondary"
              disabled={!logoFile || brandingUpload === 'logo'}
              onClick={() => uploadBranding('logo', logoFile)}
            >
              <Image size={15} />
              {brandingUpload === 'logo' ? 'Uploading…' : 'Upload logo'}
            </Button>
          </div>
          <Input
            label="Company banner URL (optional)"
            type="url"
            value={settings.banner_url || ''}
            onChange={(event) => changeSetting('banner_url', event.target.value)}
            placeholder="https://…"
          />
          <Input
            label="Company logo URL (optional)"
            type="url"
            value={settings.logo_url || ''}
            onChange={(event) => changeSetting('logo_url', event.target.value)}
            placeholder="https://…"
          />
          <div className="md:col-span-2">
            <Input
              label="Welcome message"
              value={settings.welcome_message || ''}
              maxLength={240}
              onChange={(event) => changeSetting('welcome_message', event.target.value)}
            />
          </div>
        </div>
      </Card>

      <Card>
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-violet-50 text-violet-700"><Settings2 size={19} /></span>
          <div>
            <h2 className="text-lg font-bold text-slate-950">Homepage sections</h2>
            <p className="text-sm text-slate-500">Choose what employees see and arrange the card order.</p>
          </div>
        </div>
        <div className="mt-5 space-y-2">
          {settings.section_order.map((section, index) => {
            const label = SECTION_OPTIONS.find(([key]) => key === section)?.[1] || section;
            const enabled = settings.enabled_sections.includes(section);
            return (
              <div key={section} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-100 bg-slate-50/70 p-3">
                <label className="flex items-center gap-3 text-sm font-semibold text-slate-900">
                  <input type="checkbox" checked={enabled} onChange={() => toggleSection(section)} />
                  {label}
                </label>
                <div className="flex gap-1">
                  <Button variant="ghost" size="sm" disabled={index === 0} onClick={() => moveSection(section, -1)} aria-label={`Move ${label} up`}>
                    <ArrowUp size={15} />
                  </Button>
                  <Button variant="ghost" size="sm" disabled={index === settings.section_order.length - 1} onClick={() => moveSection(section, 1)} aria-label={`Move ${label} down`}>
                    <ArrowDown size={15} />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Input
            label="New hire window (days)"
            type="number"
            min="7"
            max="180"
            value={settings.new_hire_window_days}
            onChange={(event) => changeSetting('new_hire_window_days', event.target.value)}
          />
          {[
            ['birthday_visibility_enabled', 'Enable birthdays'],
            ['anniversaries_enabled', 'Enable anniversaries'],
            ['people_statistics_enabled', 'Enable people insights'],
          ].map(([key, label]) => (
            <label key={key} className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700">
              <input type="checkbox" checked={Boolean(settings[key])} onChange={(event) => changeSetting(key, event.target.checked)} />
              {label}
            </label>
          ))}
        </div>
      </Card>

      <Card>
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-violet-50 text-violet-700"><Settings2 size={19} /></span>
          <div>
            <h2 className="text-lg font-bold text-slate-950">Ask ACE handoff</h2>
            <p className="text-sm text-slate-500">Connect an approved employee-help tool. Tenant-isolated policy retrieval is a separate integration.</p>
          </div>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-[auto_1fr] md:items-end">
          <label className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700">
            <input type="checkbox" checked={Boolean(settings.assistant_enabled)} onChange={(event) => changeSetting('assistant_enabled', event.target.checked)} />
            Enable Ask ACE
          </label>
          <Input
            label="Approved assistant URL"
            type="url"
            value={settings.assistant_url || ''}
            onChange={(event) => changeSetting('assistant_url', event.target.value)}
            placeholder="https://…"
          />
        </div>
      </Card>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-950">Events</h2>
            <p className="text-sm text-slate-500">Publish organization events that open into an employee detail card.</p>
          </div>
          <Button variant="accent" onClick={openNewEvent}><CalendarPlus size={17} /> New event</Button>
        </div>
        <div className="mt-5 space-y-2">
          {events.length ? events.map((event) => (
            <div key={event.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold text-slate-950">{event.title}</p>
                  <Badge tone={event.status === 'published' ? 'green' : event.status === 'cancelled' ? 'red' : 'slate'}>{event.status}</Badge>
                </div>
                <p className="mt-1 text-xs text-slate-500">{new Date(event.starts_at).toLocaleString()} · {event.audience}</p>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => openEditEvent(event)}><Pencil size={15} /> Edit</Button>
                <Button variant="ghost" size="sm" onClick={() => removeEvent(event.id)} aria-label={`Delete ${event.title}`}><Trash2 size={15} /></Button>
              </div>
            </div>
          )) : <p className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-500">No organization events created yet.</p>}
        </div>
      </Card>

      <Card>
        <div>
          <h2 className="text-lg font-bold text-slate-950">Essentials</h2>
          <p className="text-sm text-slate-500">Promote existing documents as required or recommended employee reading.</p>
        </div>
        <form onSubmit={addEssential} className="mt-5 grid gap-3 md:grid-cols-[1.3fr_1fr_auto_auto] md:items-end">
          <label className="block space-y-1">
            <span className="text-sm font-medium text-slate-700">Document</span>
            <select
              required
              value={essentialForm.document_id}
              onChange={(event) => setEssentialForm((current) => ({ ...current, document_id: event.target.value }))}
              className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
            >
              <option value="">Select a document</option>
              {availableDocuments.map((document) => <option key={document.id} value={document.id}>{document.title}</option>)}
            </select>
          </label>
          <Input
            label="Display title (optional)"
            value={essentialForm.display_title}
            onChange={(event) => setEssentialForm((current) => ({ ...current, display_title: event.target.value }))}
          />
          <label className="block space-y-1">
            <span className="text-sm font-medium text-slate-700">Importance</span>
            <select
              value={essentialForm.importance}
              onChange={(event) => setEssentialForm((current) => ({ ...current, importance: event.target.value }))}
              className="rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
            >
              <option value="recommended">Recommended</option>
              <option value="required">Required</option>
            </select>
          </label>
          <Button type="submit" variant="accent" disabled={saving || !essentialForm.document_id}><FilePlus2 size={16} /> Add</Button>
        </form>
        <div className="mt-5 space-y-2">
          {essentials.length ? essentials.map((item) => (
            <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
              <div>
                <p className="font-semibold text-slate-950">{item.title}</p>
                <div className="mt-1 flex gap-2"><Badge tone={item.importance === 'required' ? 'amber' : 'blue'}>{item.importance}</Badge><Badge tone={item.is_published ? 'green' : 'slate'}>{item.is_published ? 'published' : 'hidden'}</Badge></div>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => updateEssential(item, { is_published: !item.is_published })}>{item.is_published ? 'Hide' : 'Publish'}</Button>
                <Button variant="ghost" size="sm" onClick={() => removeEssential(item.id)} aria-label={`Remove ${item.title}`}><Trash2 size={15} /></Button>
              </div>
            </div>
          )) : <p className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-500">No employee essentials configured yet.</p>}
        </div>
      </Card>

      <Modal title={editingEventId ? 'Edit organization event' : 'Create organization event'} open={eventOpen} onClose={() => setEventOpen(false)} size="xl">
        <form className="space-y-5" onSubmit={saveEvent}>
          <div className="grid gap-4 md:grid-cols-2">
            <Input label="Event title" required value={eventForm.title} onChange={(event) => setEventForm((current) => ({ ...current, title: event.target.value }))} />
            <Input label="Location" value={eventForm.location} onChange={(event) => setEventForm((current) => ({ ...current, location: event.target.value }))} />
            <Input label="Starts" type="datetime-local" required value={eventForm.starts_at} onChange={(event) => setEventForm((current) => ({ ...current, starts_at: event.target.value }))} />
            <Input label="Ends" type="datetime-local" value={eventForm.ends_at} onChange={(event) => setEventForm((current) => ({ ...current, ends_at: event.target.value }))} />
            <Input label="Meeting or event URL" type="url" value={eventForm.meeting_url} onChange={(event) => setEventForm((current) => ({ ...current, meeting_url: event.target.value }))} />
            <Input label="Event image URL" type="url" value={eventForm.image_url} onChange={(event) => setEventForm((current) => ({ ...current, image_url: event.target.value }))} />
            <label className="block space-y-1">
              <span className="text-sm font-medium text-slate-700">Audience</span>
              <select value={eventForm.audience} onChange={(event) => setEventForm((current) => ({ ...current, audience: event.target.value }))} className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm">
                <option value="all">Everyone</option><option value="employees">Employees</option><option value="managers">Managers</option>
              </select>
            </label>
            <label className="block space-y-1">
              <span className="text-sm font-medium text-slate-700">Status</span>
              <select value={eventForm.status} onChange={(event) => setEventForm((current) => ({ ...current, status: event.target.value }))} className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm">
                <option value="draft">Draft</option><option value="published">Published</option><option value="cancelled">Cancelled</option>
              </select>
            </label>
          </div>
          <label className="block space-y-1">
            <span className="text-sm font-medium text-slate-700">Description</span>
            <textarea rows={5} value={eventForm.description} onChange={(event) => setEventForm((current) => ({ ...current, description: event.target.value }))} className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100" />
          </label>
          <div className="flex justify-end"><Button type="submit" variant="accent" disabled={saving}>{saving ? 'Saving…' : 'Save event'}</Button></div>
        </form>
      </Modal>
    </div>
  );
}
