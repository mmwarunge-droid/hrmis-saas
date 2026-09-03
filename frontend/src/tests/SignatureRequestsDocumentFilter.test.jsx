import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { signatureApi } from '../api/signatureApi.js';
import SignatureRequests from '../pages/SignatureRequests.jsx';

vi.mock('../api/signatureApi.js', () => ({
  signatureApi: {
    list: vi.fn(),
    get: vi.fn(),
    evidence: vi.fn(),
    remind: vi.fn(),
    updateDeadline: vi.fn(),
    cancel: vi.fn(),
    applySeal: vi.fn(),
    retryEvidence: vi.fn(),
  },
}));

vi.mock('../components/documents/SignatureRequestDetails.jsx', () => ({
  default: ({ request, onApplySeal }) => (
    <div>
      <p>Seal state: {request.seal_status || 'none'}</p>
      {onApplySeal && (
        <button
          type="button"
          onClick={() => onApplySeal(request.id)}
        >
          Apply Company Seal
        </button>
      )}
    </div>
  ),
}));

beforeEach(() => {
  vi.clearAllMocks();

  signatureApi.list.mockResolvedValue({
    data: { items: [] },
  });
});

test(
  'filters signature requests by the document selected from Files',
  async () => {
    render(
      <MemoryRouter
        initialEntries={[
          '/signature-requests?document_id=document-1',
        ]}
      >
        <SignatureRequests />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(signatureApi.list).toHaveBeenCalledWith({
        document_id: 'document-1',
      });
    });
  },
);

test(
  'applies a pending company seal and refreshes management details',
  async () => {
    const pendingRequest = {
      id: 'request-1',
      subject: 'Employment contract approval',
      status: 'completed',
      assurance_level: 'aes',
      current_sequence: 1,
      recipient_count: 1,
      signed_count: 1,
      due_at: '2099-08-20T17:00:00Z',
      seal_required: true,
      seal_status: 'pending',
      document: {
        id: 'document-1',
        title: 'Employment contract',
      },
      recipients: [
        {
          id: 'recipient-1',
          name: 'Amina Otieno',
          sequence: 1,
          status: 'signed',
        },
      ],
    };
    const appliedRequest = {
      ...pendingRequest,
      seal_status: 'applied',
      sealed_at: '2026-09-03T09:30:00Z',
      sealed_document: {
        id: 'sealed-artifact-1',
        artifact_type: 'sealed_document',
      },
    };

    signatureApi.list.mockResolvedValue({
      data: { items: [pendingRequest] },
    });
    signatureApi.get
      .mockResolvedValueOnce({ data: pendingRequest })
      .mockResolvedValueOnce({ data: appliedRequest });
    signatureApi.applySeal.mockResolvedValue({
      data: {},
    });

    render(
      <MemoryRouter initialEntries={['/signature-requests']}>
        <SignatureRequests />
      </MemoryRouter>,
    );

    fireEvent.click(
      await screen.findByRole('button', {
        name: 'View details',
      }),
    );

    expect(
      await screen.findByText('Seal state: pending'),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Apply Company Seal',
      }),
    );

    await waitFor(() => {
      expect(signatureApi.applySeal).toHaveBeenCalledWith(
        'request-1',
      );
    });

    expect(signatureApi.get).toHaveBeenCalledTimes(2);

    expect(
      await screen.findByText('Seal state: applied'),
    ).toBeInTheDocument();
  },
);
