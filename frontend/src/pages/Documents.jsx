import {
  useCallback,
  useEffect,
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
import Input from '../components/ui/Input.jsx';
import Modal from '../components/ui/Modal.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import StatCard from '../components/ui/StatCard.jsx';
import Table from '../components/ui/Table.jsx';
import usePermissions from '../hooks/usePermissions';

const PAGE_SIZE = 15;
const EMPTY_META = {
  page: 1,
  per_page: PAGE_SIZE,
  total: 0,
  pages: 1,
};
const EMPTY_SUMMARY = {
  total: 0,
  awaiting_signature: 0,
  signed: 0,
  expiring_soon: 0,
  folders: [],
};

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
  const [meta, setMeta] = useState(EMPTY_META);
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [signatureSaving, setSignatureSaving] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [signatureOpen, setSignatureOpen] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [query, setQuery] = useState('');
  const [folder, setFolder] = useState('all');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState(null);

  const { hasPermission, hasRole } = usePermissions();
  const isSuperAdmin = hasRole('SUPER_ADMIN');
  const canManageSignatures = hasPermission('document:approve');

  const loadReferenceData = useCallback(async () => {
    try {
      const [employeesResponse, tenantsResponse] = await Promise.all([
        canManageSignatures
          ? employeeApi.options()
          : Promise.resolve({ data: { items: [] } }),
        isSuperAdmin
          ? tenantApi.list({ per_page: 100 })
          : Promise.resolve({ data: { items: [] } }),
      ]);

      setEmployees(employeesResponse.data.items || []);
      setTenants(tenantsResponse.data.items || []);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to load document reference data',
      );
    }
  }, [canManageSignatures, isSuperAdmin]);

  const loadSummary = useCallback(async () => {
    try {
      const response = await documentApi.summary();
      setSummary(response.data || EMPTY_SUMMARY);
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to load document totals',
      );
    }
  }, []);

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const response = await documentApi.list({
        page,
        per_page: PAGE_SIZE,
        q: query || undefined,
        document_type: folder === 'all' ? undefined : folder,
        sort: sort?.key || undefined,
        direction: sort?.direction || undefined,
      });
      setDocuments(response.data.items || []);
      setMeta(response.data.meta || {
        ...EMPTY_META,
        page,
      });
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to load document library',
      );
    } finally {
      setLoading(false);
    }
  }, [folder, page, query, sort]);

  useEffect(() => {
    loadReferenceData();
    loadSummary();
  }, [loadReferenceData, loadSummary]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const refreshLibrary = async () => {
    await Promise.all([loadDocuments(), loadSummary()]);
  };

  const upload = async (formData) => {
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      await documentApi.upload(formData);
      setUploadOpen(false);
      setSuccess('Document uploaded successfully.');
      setPage(1);
      await refreshLibrary();
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

      await refreshLibrary();
    } catch (err) {
      setError(
        err.error?.message
        || 'Unable to send signature request',
      );
    } finally {
      setSignatureSaving(false);
    }
  };

  const updateQuery = (value) => {
    setQuery(value);
    setPage(1);
  };

  const updateFolder = (value) => {
    setFolder(value);
    setPage(1);
  };

  const updateSort = (value) => {
    setSort(value);
    setPage(1);
  };

  const columns = [
    {
      key: 'title',
      label: 'File',
      sortable: true,
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
      sortable: true,
      render: (row) => (
        <Badge tone="blue">
          {row.document_type}
        </Badge>
      ),
    },
    {
      key: 'signature_status',
      label: 'Signature',
      sortable: true,
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
      sortable: true,
      render: (row) => (
        <Badge tone={row.status === 'active' ? 'green' : 'amber'}>
          {row.status}
        </Badge>
      ),
    },
    {
      key: 'size_bytes',
      label: 'Size',
      sortable: true,
      render: (row) => formatSize(row.size_bytes),
    },
    {
      key: 'expiry_date',
      label: 'Expiry',
      sortable: true,
      render: (row) => row.expiry_date || '—',
    },
    {
      key: 'actions',
      label: '',
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
    <div className="space-y-6">
      <PageHeader
        eyebrow="Files"
        title="Files"
        description="Store, find, distribute, and track contracts, policies, and employee files from one governed workspace."
        actions={(
          <>
            {hasPermission('document:upload') && (
              <Button
                variant="accent"
                onClick={() => setUploadOpen(true)}
              >
                <Plus size={17} />
                Upload file
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
          value={summary.total}
          detail={`${summary.folders.length} document folders`}
          icon={FileStack}
          tone="blue"
        />
        <StatCard
          label="Awaiting signature"
          value={summary.awaiting_signature}
          detail="Active signing workflows"
          icon={FileSignature}
          tone="violet"
        />
        <StatCard
          label="Signed"
          value={summary.signed}
          detail="Completed signature workflows"
          icon={FileCheck2}
          tone="emerald"
        />
        <StatCard
          label="Expiring soon"
          value={summary.expiring_soon}
          detail="Within the next 30 days"
          icon={FileClock}
          tone="amber"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[260px_1fr]">
        <Card>
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-lg bg-blue-50 text-blue-700">
              <Folder size={19} />
            </span>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
                Folders
              </p>
              <h2 className="font-bold">Library</h2>
            </div>
          </div>

          <div className="mt-5 space-y-1">
            <button
              type="button"
              aria-label={`Show all documents (${summary.total})`}
              aria-pressed={folder === 'all'}
              onClick={() => updateFolder('all')}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm font-medium ${
                folder === 'all'
                  ? 'bg-blue-50 text-blue-800'
                  : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <span>All documents</span>
              <span>{summary.total}</span>
            </button>

            {summary.folders.map((item) => (
              <button
                type="button"
                key={item.document_type}
                aria-label={`Show ${item.document_type.replaceAll('_', ' ')} documents (${item.count})`}
                aria-pressed={folder === item.document_type}
                onClick={() => updateFolder(item.document_type)}
                className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm font-medium ${
                  folder === item.document_type
                    ? 'bg-blue-50 text-blue-800'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                <span className="truncate">
                  {item.document_type.replaceAll('_', ' ')}
                </span>
                <span>{item.count}</span>
              </button>
            ))}
          </div>

          <div className="mt-6 rounded-lg bg-blue-50 p-4 text-blue-900">
            <ShieldCheck size={19} />
            <p className="mt-3 text-sm font-semibold">
              Access-aware by design
            </p>
            <p className="mt-1 text-xs leading-5 text-blue-700">
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
                aria-label="Search documents"
                className="pl-10"
                placeholder="Search titles, files or folders"
                value={query}
                onChange={(event) => updateQuery(event.target.value)}
              />
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Showing {documents.length} of {meta.total} matching documents
            </p>
          </Card>

          <Table
            columns={columns}
            rows={documents}
            loading={loading}
            empty="No documents match the current search and folder."
            caption="File library"
            sort={sort}
            onSortChange={updateSort}
            pagination={{
              page: meta.page,
              pageSize: meta.per_page,
              total: meta.total,
              onPageChange: setPage,
              label: 'documents',
            }}
          />
        </div>
      </div>

      <Modal
        title="Upload file"
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
