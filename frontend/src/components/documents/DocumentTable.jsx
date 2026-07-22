import Table from '../ui/Table.jsx';
import { documentApi } from '../../api/documentApi';

export default function DocumentTable({ documents }) {
  const columns = [
    { key: 'title', label: 'Title' },
    { key: 'document_type', label: 'Type' },
    { key: 'signature_status', label: 'Signature' },
    { key: 'expiry_date', label: 'Expiry' },
    { key: 'download', label: 'File', render: (row) => <a className="font-medium text-slate-950 underline" href={documentApi.downloadUrl(row.id)} target="_blank" rel="noreferrer">Download</a> },
  ];
  return <Table columns={columns} rows={documents} empty="No documents uploaded." />;
}
