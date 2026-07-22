import { useEffect, useState } from 'react';
import { documentApi } from '../api/documentApi';
import DocumentTable from '../components/documents/DocumentTable.jsx';
import DocumentUpload from '../components/documents/DocumentUpload.jsx';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Modal from '../components/ui/Modal.jsx';
import Spinner from '../components/ui/Spinner.jsx';
import usePermissions from '../hooks/usePermissions';

export default function Documents() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const { hasPermission } = usePermissions();
  const load = () => documentApi.list().then((res) => setDocuments(res.data.items)).catch((err) => setError(err.error?.message || 'Load failed')).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);
  const upload = async (formData) => { setSaving(true); try { await documentApi.upload(formData); setOpen(false); await load(); } catch (err) { setError(err.error?.message || 'Upload failed'); } finally { setSaving(false); } };
  return <div className="space-y-6"><div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold">Documents</h1><p className="text-slate-500">Compliance-ready secure repository.</p></div>{hasPermission('document:upload') && <Button onClick={() => setOpen(true)}>Upload</Button>}</div>{error && <Alert type="error">{error}</Alert>}{loading ? <Spinner /> : <DocumentTable documents={documents} />}<Modal title="Upload Document" open={open} onClose={() => setOpen(false)}><DocumentUpload onSubmit={upload} loading={saving} /></Modal></div>;
}
