import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  FileCheck2,
  FileClock,
  FileSignature,
  FileStack,
  Folder,
  PenLine,
  Plus,
  Search,
  ShieldCheck,
} from 'lucide-react';

import { documentApi } from '../api/documentApi';
import { employeeApi } from '../api/employeeApi';
import { signatureApi } from '../api/signatureApi';
import { tenantApi } from '../api/tenantApi';
import DocumentUpload from '../components/documents/DocumentUpload.jsx';
import SignatureRequestForm from '../components/documents/SignatureRequestForm.jsx';
import Alert from '../components/ui/Alert.jsx';
import Badge from '../components/ui/Badge.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import Input from '../components/ui/Input.jsx';
import Modal from '../components/ui/Modal.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import Table from '../components/ui/Table.jsx';
import usePermissions from '../hooks/usePermissions';

function formatSize(bytes) {
  if (!bytes) return '—';

  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Documents() {
  const [documents, setDocuments] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [saving, setSaving] = useState(false);
  const [signatureSaving, setSignatureSaving] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [signatureOpen, setSignatureOpen] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [query, setQuery] = useState('');
  const [folder, setFolder] = useState('all');

  const { hasPermission, hasRole } = usePermissions();
  const isSuperAdmin = hasRole('SUPER_ADMIN');
  const canManageSignatures = hasPermission(
    'document:approve',
  );

  const load = useCallback(async () => {
    try {
      const [
        documentsResponse,
        employeesResponse,
        tenantsResponse,
      ] = await Promise.all([
        documentApi.list(),
        canManageSignatures
          ? employeeApi.list({ per_page: 100 })
          : Promise.resolve({ data: { items: [] } }),
        isSuperAdmin
          ? tenantApi.list()
          : Promise.resolve({ data: { items: [] } }),
      ]);

      setDocuments(documentsResponse.data.items || []);
      setEmployees(employeesResponse.data.items || []);
      setTenants(tenantsResponse.data.items || []);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to load document library',
      );
    }
  }, [canManageSignatures, isSuperAdmin]);

  useEffect(() => {
    load();
  }, [load]);

  const folders = useMemo(
    () => [
      ...new Set(
        documents
          .map((document) => document.document_type)
          .filter(Boolean),
      ),
    ],
    [documents],
  );

  const filtered = useMemo(
    () => documents.filter((document) => {
      const matchesFolder = (
        folder === 'all'
        || document.document_type === folder
      );
      const searchable = [
        document.title,
        document.original_filename,
        document.document_type,
      ].join(' ').toLowerCase();

      const matchesQuery = (
        !query
        || searchable.includes(query.toLowerCase())
      );

      return matchesFolder && matchesQuery;
    }),
    [documents, folder, query],
  );

  const signed = documents.filter(
    (document) => document.signature_status === 'signed',
  ).length;

  const pending = documents.filter(
    (document) => document.signature_status === 'pending',
  ).length;

  const expiring = documents.filter((document) => (
    document.expiry_date
    && new Date(`${document.expiry_date}T00:00:00`)
      <= new Date(Date.now() + 30 * 86400000)
  )).length;

  const upload = async (formData) => {
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      await documentApi.upload(formData);
      setUploadOpen(false);
      setSuccess('Document uploaded successfully.');
      await load();
    } catch (err) {
      setError(err.error?.message || 'Upload failed');
    } finally {
      setSaving(false);
    }
  };

  const openSignatureRequest = (document) => {
    setSelectedDocument(document);
    setSignatureOpen(true);
    setError('');
    setSuccess('');
  };

  const closeSignatureRequest = () => {
    if (signatureSaving) return;

    setSignatureOpen(false);
    setSelectedDocument(null);
  };

  const sendSignatureRequest = async (payload) => {
    setSignatureSaving(true);
    setError('');
    setSuccess('');

    try {
      const response = await signatureApi.create(payload);

      setSignatureOpen(false);
      setSelectedDocument(null);
      setSuccess(
        response.data.assurance_level === 'qes'
          ? (
            `${response.data.subject} was submitted to Dropbox `
            + 'Sign. The signatory will receive a provider-hosted '
            + 'eID invitation by email.'
          )
          : (
            `${response.data.subject} was sent to `
            + `${response.data.recipient_count} signatory`
            + `${response.data.recipient_count === 1 ? '' : 'ies'}.`
          ),
      );

      await load();
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to send signature request',
      );
    } finally {
      setSignatureSaving(false);
    }
  };

  const columns = [
    {
      key: 'title',
      label: 'Document',
      render: (row) => (
        <div>
          <p className="font-semibold text-slate-900">
            {row.title}
          </p>
          <p className="text-xs text-slate-500">
            {row.original_filename}
          </p>
        </div>
      ),
    },
    {
      key: 'document_type',
      label: 'Folder',
      render: (row) => (
        <Badge tone="blue">
          {row.document_type}
        </Badge>
      ),
    },
    {
      key: 'signature_status',
      label: 'Signature',
      render: (row) => (
        <Badge
          tone={
            row.signature_status === 'signed'
              ? 'green'
              : row.signature_status === 'pending'
                ? 'amber'
                : row.signature_status === 'declined'
                  ? 'red'
                  : 'slate'
          }
        >
          {row.signature_status.replaceAll('_', ' ')}
        </Badge>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      render: (row) => (
        <Badge tone={row.status === 'active' ? 'green' : 'amber'}>
          {row.status}
        </Badge>
      ),
    },
    {
      key: 'size_bytes',
      label: 'Size',
      render: (row) => formatSize(row.size_bytes),
    },
    {
      key: 'expiry_date',
      label: 'Expiry',
      render: (row) => row.expiry_date || '—',
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (row) => (
        canManageSignatures && row.status === 'active'
          ? (
            <Button
              type="button"
              size="sm"
              variant="soft"
              disabled={row.signature_status === 'signed'}
              onClick={() => openSignatureRequest(row)}
            >
              <PenLine size={14} />
              Send for signature
            </Button>
          )
          : '—'
      ),
    },
  ];

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Docs"
        title="Document library"
        description="Upload, control, distribute and track contracts, policies and employee documents from one governed workspace."
        actions={(
          <>
            {hasPermission('document:upload') && (
              <Button
                variant="accent"
                onClick={() => setUploadOpen(true)}
              >
                <Plus size={17} />
                Upload document
              </Button>
            )}
          </>
        )}
      />

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard
          label="Documents"
          value={documents.length}
          detail={`${folders.length} document folders`}
          icon={FileStack}
          tone="blue"
        />
        <StatCard
          label="Awaiting signature"
          value={pending}
          detail="Active signing workflows"
          icon={FileSignature}
          tone="violet"
        />
        <StatCard
          label="Signed"
          value={signed}
          detail="Completed signature workflows"
          icon={FileCheck2}
          tone="emerald"
        />
        <StatCard
          label="Expiring soon"
          value={expiring}
          detail="Within the next 30 days"
          icon={FileClock}
          tone="amber"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[260px_1fr]">
        <Card>
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-2xl bg-cyan-50 text-cyan-700">
              <Folder size={19} />
            </span>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-cyan-700">
                Folders
              </p>
              <h2 className="font-bold">Library</h2>
            </div>
          </div>

          <div className="mt-5 space-y-1">
            <button
              type="button"
              onClick={() => setFolder('all')}
              className={`flex w-full items-center justify-between rounded-2xl px-3 py-2 text-left text-sm font-medium ${
                folder === 'all'
                  ? 'bg-slate-950 text-white'
                  : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <span>All documents</span>
              <span>{documents.length}</span>
            </button>

            {folders.map((item) => (
              <button
                type="button"
                key={item}
                onClick={() => setFolder(item)}
                className={`flex w-full items-center justify-between rounded-2xl px-3 py-2 text-left text-sm font-medium ${
                  folder === item
                    ? 'bg-slate-950 text-white'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                <span className="truncate">
                  {item.replaceAll('_', ' ')}
                </span>
                <span>
                  {
                    documents.filter(
                      (document) => (
                        document.document_type === item
                      ),
                    ).length
                  }
                </span>
              </button>
            ))}
          </div>

          <div className="mt-6 rounded-2xl bg-violet-50 p-4 text-violet-900">
            <ShieldCheck size={19} />
            <p className="mt-3 text-sm font-semibold">
              Access-aware by design
            </p>
            <p className="mt-1 text-xs leading-5 text-violet-700">
              Employee, manager, HR-only and company-admin
              access levels are preserved.
            </p>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-3 top-3 text-slate-400"
                size={18}
              />
              <Input
                className="pl-10"
                placeholder="Search titles, files or folders"
                value={query}
                onChange={(event) => setQuery(
                  event.target.value,
                )}
              />
            </div>
          </Card>

          {filtered.length === 0 ? (
            <EmptyState
              title="No documents found"
              description="Try another folder, clear the search or upload a document."
            />
          ) : (
            <Table columns={columns} rows={filtered} />
          )}
        </div>
      </div>

      <Modal
        title="Upload document"
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
      >
        <DocumentUpload
          onSubmit={upload}
          loading={saving}
          isSuperAdmin={isSuperAdmin}
          tenants={tenants}
        />
      </Modal>

      <Modal
        title="Send document for signature"
        open={signatureOpen}
        onClose={closeSignatureRequest}
        size="xl"
      >
        <SignatureRequestForm
          document={selectedDocument}
          employees={employees}
          isSuperAdmin={isSuperAdmin}
          loading={signatureSaving}
          onSubmit={sendSignatureRequest}
        />
      </Modal>
    </div>
  );
}
