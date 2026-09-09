import { useState } from 'react';
import { signatureApi } from '../../api/signatureApi.js';
import Button from '../ui/Button.jsx';

export default function SignatureTemplatePicker({ employees, tenants, isSuperAdmin, onSelect }) {
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState('');
  const [employeeId, setEmployeeId] = useState('');
  const [tenantId, setTenantId] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setBusy(true); setError('');
    try { const response = await signatureApi.templates(isSuperAdmin ? { tenant_id: tenantId } : {}); setTemplates(response.data.items); }
    catch (err) { setError(err.error?.message || 'Unable to load templates.'); }
    finally { setBusy(false); }
  };
  const review = async () => {
    setBusy(true); setError('');
    try { const response = await signatureApi.useTemplate(templateId, employeeId, isSuperAdmin ? tenantId : null); onSelect(response.data); }
    catch (err) { setError(err.error?.message || 'Unable to prepare template.'); }
    finally { setBusy(false); }
  };
  return <section className="space-y-3 rounded-xl border bg-white p-4">
    <h2 className="font-semibold">Reusable signing templates</h2>
    {isSuperAdmin && <select aria-label="Template organization" value={tenantId} onChange={(e) => { setTenantId(e.target.value); setTemplates([]); setTemplateId(''); }}>
      <option value="">Select organization</option>{tenants.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
    </select>}
    <Button type="button" variant="secondary" disabled={busy || (isSuperAdmin && !tenantId)} onClick={load}>Browse templates</Button>
    <div className="flex flex-wrap gap-3">
      <select aria-label="Signing template" value={templateId} onChange={(e) => setTemplateId(e.target.value)} className="rounded border p-2">
        <option value="">Select template</option>{templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
      </select>
      <select aria-label="Template employee" value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} className="rounded border p-2">
        <option value="">Select employee</option>{employees.filter((e) => !isSuperAdmin || String(e.tenant_id) === tenantId).map((e) => <option key={e.id} value={e.id}>{e.full_name}</option>)}
      </select>
      <Button type="button" disabled={busy || !templateId || !employeeId} onClick={review}>Review and assign signers</Button>
    </div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
  </section>;
}
