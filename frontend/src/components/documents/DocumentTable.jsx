import Table from '../ui/Table.jsx';

export default function DocumentTable({ documents }) {
  const columns = [
    { key: 'title', label: 'Title' },
    { key: 'document_type', label: 'Type' },
    { key: 'signature_status', label: 'Signature' },
    { key: 'expiry_date', label: 'Expiry' },
    { key: 'review', label: 'File', render: (row) => <a className="font-medium text-blue-700 underline" href={`/documents/${row.id}/review`} target="_blank" rel="noreferrer">Review</a> },
  ];
  return <Table columns={columns} rows={documents} empty="No documents uploaded." />;
}
