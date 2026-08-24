import { useEffect, useState } from 'react';
import { BriefcaseBusiness, Save } from 'lucide-react';

import { tenantApi } from '../api/tenantApi.js';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import useTenant from '../hooks/useTenant.js';

function normalizeTitles(value) {
  const seen = new Set();
  const titles = [];

  String(value || '')
    .split(/\r?\n/)
    .forEach((item) => {
      const title = item.trim();
      if (!title) return;

      const key = title.toLowerCase();
      if (seen.has(key)) return;

      seen.add(key);
      titles.push(title);
    });

  return titles;
}

export default function EmploymentGovernanceSettings() {
  const { tenantId } = useTenant();
  const [titlesText, setTitlesText] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!tenantId) {
      setLoaded(false);
      return;
    }

    let active = true;

    const load = async () => {
      setLoaded(false);
      setError('');
      setMessage('');

      try {
        const response = await tenantApi.employmentGovernance(tenantId);
        if (!active) return;

        setTitlesText(
          (
            response.data.duplicate_job_title_warning_titles || []
          ).join('\n'),
        );
        setLoaded(true);
      } catch (err) {
        if (!active) return;

        setError(
          err.error?.message
          || 'Unable to load employment governance settings.',
        );
      }
    };

    load();

    return () => {
      active = false;
    };
  }, [tenantId]);

  const save = async () => {
    const titles = normalizeTitles(titlesText);

    setSaving(true);
    setError('');
    setMessage('');

    try {
      const response = await tenantApi.updateEmploymentGovernance(
        tenantId,
        {
          duplicate_job_title_warning_titles: titles,
        },
      );

      const savedTitles = (
        response.data.duplicate_job_title_warning_titles || []
      );

      setTitlesText(savedTitles.join('\n'));
      setMessage('Employment governance settings saved.');
    } catch (err) {
      setError(
        err.error?.message
        || 'Employment governance settings could not be saved.',
      );
    } finally {
      setSaving(false);
    }
  };

  if (!tenantId) {
    return (
      <Alert>
        Select an organization before configuring employment governance.
      </Alert>
    );
  }

  if (!loaded) {
    return error ? (
      <Alert type="error">{error}</Alert>
    ) : (
      <div className="h-72 animate-pulse rounded-xl bg-slate-100" />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administration"
        title="Employment governance"
        description={
          'Configure advisory controls for organizational employment '
          + 'structures without blocking legitimate staffing models.'
        }
        actions={(
          <Button
            variant="accent"
            onClick={save}
            disabled={saving}
          >
            <Save size={17} />
            {saving ? 'Saving…' : 'Save governance'}
          </Button>
        )}
      />

      {error && <Alert type="error">{error}</Alert>}
      {message && <Alert type="success">{message}</Alert>}

      <Card>
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-700">
            <BriefcaseBusiness size={19} />
          </span>
          <div>
            <h2 className="text-lg font-bold text-slate-950">
              Duplicate job-title confirmations
            </h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              Add job titles where administrators should receive a warning
              before assigning the same title to another employee. This is an
              advisory confirmation, not a uniqueness restriction.
            </p>
          </div>
        </div>

        <label className="mt-5 block space-y-2">
          <span className="text-sm font-semibold text-slate-700">
            Job titles that require duplicate confirmation
          </span>
          <textarea
            rows={9}
            value={titlesText}
            onChange={(event) => setTitlesText(event.target.value)}
            placeholder={'CEO\nChief Financial Officer\nCountry Director'}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
          />
          <span className="block text-xs leading-5 text-slate-500">
            Enter one job title per line. Matching ignores capitalization and
            surrounding spaces. Duplicate entries are removed when saved.
          </span>
        </label>
      </Card>
    </div>
  );
}
