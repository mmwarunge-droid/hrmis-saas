import { useEffect, useState } from 'react';
import { ArrowLeft, CalendarDays, ExternalLink, MapPin } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { employeeHomeApi } from '../api/employeeHomeApi.js';
import Alert from '../components/ui/Alert.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';

function formatDateTime(value) {
  if (!value) return 'Not set';
  return new Intl.DateTimeFormat('en', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
}

export default function OrganizationEventDetails() {
  const { id } = useParams();
  const [event, setEvent] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    employeeHomeApi.event(id)
      .then((response) => {
        if (active) setEvent(response.data);
      })
      .catch((err) => {
        if (active) setError(err.error?.message || 'Unable to load this event.');
      });
    return () => { active = false; };
  }, [id]);

  if (error) return <Alert type="error">{error}</Alert>;
  if (!event) return <div className="h-96 animate-pulse rounded-xl bg-slate-100" />;

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <Link to="/dashboard" className="inline-flex items-center gap-2 text-sm font-semibold text-blue-800">
        <ArrowLeft size={16} /> Back home
      </Link>
      <Card padded={false} className="overflow-hidden">
        {event.image_url ? (
          <img src={event.image_url} alt="" className="h-64 w-full object-cover md:h-80" />
        ) : (
          <div className="h-48 bg-gradient-to-br from-blue-700 via-blue-800 to-blue-700" />
        )}
        <div className="p-6 md:p-9">
          <Badge tone={event.status === 'cancelled' ? 'red' : 'violet'}>{event.status}</Badge>
          <h1 className="mt-4 text-3xl font-bold text-slate-950 md:text-4xl">{event.title}</h1>
          <div className="mt-6 grid gap-3 text-sm text-slate-600 md:grid-cols-2">
            <p className="flex items-start gap-2">
              <CalendarDays size={17} className="mt-0.5 text-blue-700" />
              <span>
                <b className="text-slate-900">Starts:</b> {formatDateTime(event.starts_at)}
                {event.ends_at && <><br /><b className="text-slate-900">Ends:</b> {formatDateTime(event.ends_at)}</>}
              </span>
            </p>
            <p className="flex items-start gap-2">
              <MapPin size={17} className="mt-0.5 text-blue-700" />
              <span>{event.location || 'Location to be confirmed'}</span>
            </p>
          </div>
          {event.description && (
            <p className="mt-7 whitespace-pre-wrap text-sm leading-7 text-slate-700">{event.description}</p>
          )}
          {event.meeting_url && (
            <a href={event.meeting_url} target="_blank" rel="noreferrer" className="mt-7 inline-flex">
              <Button variant="accent">
                Open event link <ExternalLink size={16} />
              </Button>
            </a>
          )}
        </div>
      </Card>
    </div>
  );
}
