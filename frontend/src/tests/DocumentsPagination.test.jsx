import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom';

import { documentApi } from '../api/documentApi.js';
import { employeeApi } from '../api/employeeApi.js';
import { tenantApi } from '../api/tenantApi.js';
import usePermissions from '../hooks/usePermissions.js';
import Documents from '../pages/Documents.jsx';

vi.mock(
  '../components/documents/SignatureFieldPlacement.jsx',
  () => ({
    default: () => null,
  }),
);

vi.mock('../api/documentApi.js', () => ({
  documentApi: {
    list: vi.fn(),
    summary: vi.fn(),
    upload: vi.fn(),
  },
}));

vi.mock('../api/employeeApi.js', () => ({
  employeeApi: {
    options: vi.fn(),
  },
}));

vi.mock('../api/signatureApi.js', () => ({
  signatureApi: {
    create: vi.fn(),
  },
}));

vi.mock('../api/tenantApi.js', () => ({
  tenantApi: {
    options: vi.fn(),
    list: vi.fn(),
  },
}));

vi.mock('../hooks/usePermissions.js', () => ({
  default: vi.fn(),
}));

function document(index) {
  return {
    id: `document-${index}`,
    title: `Document ${String(index).padStart(2, '0')}`,
    original_filename: `document-${index}.pdf`,
    document_type: index % 2 === 0 ? 'contract' : 'policy',
    signature_status: index < 5 ? 'pending' : 'signed',
    status: 'active',
    size_bytes: 1024,
    expiry_date: null,
  };
}

function LocationProbe() {
  const location = useLocation();

  return (
    <div data-testid="location">
      {location.pathname}{location.search}
    </div>
  );
}

beforeEach(() => {
  vi.clearAllMocks();

  usePermissions.mockReturnValue({
    hasPermission: () => false,
    hasRole: () => false,
  });

  employeeApi.options.mockResolvedValue({
    data: { items: [] },
  });
  tenantApi.options.mockResolvedValue({
    data: { items: [] },
  });
  documentApi.summary.mockResolvedValue({
    data: {
      total: 35,
      awaiting_signature: 5,
      signed: 24,
      expiring_soon: 3,
      folders: [
        { document_type: 'contract', count: 20 },
        { document_type: 'policy', count: 15 },
      ],
    },
  });
  documentApi.list.mockImplementation((params) => {
    const page = params.page || 1;
    const start = ((page - 1) * 15) + 1;
    return Promise.resolve({
      data: {
        items: Array.from(
          { length: page === 3 ? 5 : 15 },
          (_, offset) => document(start + offset),
        ),
        meta: {
          page,
          per_page: 15,
          total: 35,
          pages: 3,
        },
      },
    });
  });
});

test('uses access-scoped document totals and server pagination', async () => {
  render(
    <MemoryRouter>
      <Documents />
    </MemoryRouter>,
  );

  expect(
    await screen.findByText('Showing 15 of 35 matching documents'),
  ).toBeInTheDocument();
  expect(screen.getByText('1–15 of 35 documents')).toBeInTheDocument();
  expect(screen.getByText('Awaiting signature').closest('section'))
    .toHaveTextContent('5');
  expect(screen.getByRole('button', { name: /all documents/i }))
    .toHaveTextContent('35');

  fireEvent.click(screen.getByRole('button', { name: /next page/i }));

  await waitFor(() => {
    expect(documentApi.list).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 2,
        per_page: 15,
      }),
    );
  });

  fireEvent.change(screen.getByLabelText('Search documents'), {
    target: { value: 'policy' },
  });

  await waitFor(() => {
    expect(documentApi.list).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        q: 'policy',
      }),
    );
  });

  fireEvent.click(screen.getByRole('button', { name: /show policy documents/i }));

  await waitFor(() => {
    expect(documentApi.list).toHaveBeenCalledWith(
      expect.objectContaining({
        document_type: 'policy',
      }),
    );
  });

  fireEvent.click(screen.getByRole('button', { name: 'File' }));

  await waitFor(() => {
    expect(documentApi.list).toHaveBeenCalledWith(
      expect.objectContaining({
        sort: 'title',
        direction: 'asc',
      }),
    );
  });
});

test('routes pending documents to the existing signing workflow', async () => {
  usePermissions.mockReturnValue({
    hasPermission: (permission) => permission === 'document:approve',
    hasRole: () => false,
  });

  documentApi.list.mockResolvedValue({
    data: {
      items: [{
        ...document(1),
        signature_status: 'pending',
      }],
      meta: {
        page: 1,
        per_page: 15,
        total: 1,
        pages: 1,
      },
    },
  });

  render(
    <MemoryRouter initialEntries={['/documents']}>
      <Routes>
        <Route path="/documents" element={<Documents />} />
        <Route
          path="/signature-requests"
          element={<LocationProbe />}
        />
      </Routes>
    </MemoryRouter>,
  );

  const manageButton = await screen.findByRole(
    'button',
    { name: 'Manage signing' },
  );

  expect(
    screen.queryByRole(
      'button',
      { name: 'Send for signature' },
    ),
  ).not.toBeInTheDocument();

  fireEvent.click(manageButton);

  expect(
    await screen.findByTestId('location'),
  ).toHaveTextContent(
    '/signature-requests?document_id=document-1',
  );
});

test('allows a new request after a document workflow has expired', async () => {
  usePermissions.mockReturnValue({
    hasPermission: (permission) => permission === 'document:approve',
    hasRole: () => false,
  });

  documentApi.list.mockResolvedValue({
    data: {
      items: [{
        ...document(1),
        signature_status: 'expired',
      }],
      meta: {
        page: 1,
        per_page: 15,
        total: 1,
        pages: 1,
      },
    },
  });

  render(
    <MemoryRouter>
      <Documents />
    </MemoryRouter>,
  );

  fireEvent.click(
    await screen.findByRole(
      'button',
      { name: 'Send for signature' },
    ),
  );

  expect(
    screen.getByText('Send document for signature'),
  ).toBeInTheDocument();
});
