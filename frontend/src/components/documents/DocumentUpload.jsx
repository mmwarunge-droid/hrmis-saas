import { useState } from 'react';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';

export default function DocumentUpload({ onSubmit, loading = false }) {
  const [form, setForm] = useState({ title: '', document_type: 'contract', access_level: 'hr_only', expiry_date: '' });
  const [file, setFile] = useState(null);
  const submit = (e) => {
    e.preventDefault();
    const data = new FormData();
    Object.entries(form).forEach(([key, value]) => value && data.append(key, value));
    if (file) data.append('file', file);
    onSubmit(data);
  };
  return (
    <form onSubmit={submit} className="space-y-4">
      <Input label="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
      <select className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.document_type} onChange={(e) => setForm({ ...form, document_type: e.target.value })}><option value="contract">Contract</option><option value="policy">Policy</option><option value="tax">Tax</option><option value="certification">Certification</option><option value="id">ID</option><option value="other">Other</option></select>
      <Input label="Expiry date" type="date" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} />
      <input type="file" onChange={(e) => setFile(e.target.files[0])} required className="block w-full text-sm" />
      <Button disabled={loading}>{loading ? 'Uploading...' : 'Upload document'}</Button>
    </form>
  );
}
