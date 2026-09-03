import {
  render,
  screen,
} from '@testing-library/react';
import {
  describe,
  expect,
  it,
  vi,
} from 'vitest';

vi.mock(
  '../components/documents/SignatureSealPlacement.jsx',
  () => ({
    default: ({ request, seal }) => (
      <div data-testid="seal-placement-editor">
        Signed artifact: {request.signed_document?.id}
        {' | '}
        Seal page: {seal?.page_number ?? 'none'}
      </div>
    ),
  }),
);

import SignatureRequestDetails from '../components/documents/SignatureRequestDetails.jsx';

const baseRequest = {
  id: 'request-1',
  subject: 'Employment contract',
  status: 'completed',
  signing_mode: 'sequential',
  current_sequence: 1,
  due_at: '2099-08-20T17:00:00Z',
  recipient_count: 1,
  signed_count: 1,
  assurance_level: 'standard',
  seal_required: true,
  signed_document: {
    id: 'signed-artifact-1',
    artifact_type: 'signed_document',
  },
  document: {
    id: 'document-1',
    title: 'Employment contract',
  },
  recipients: [{
    id: 'recipient-1',
    name: 'Amina Otieno',
    email: 'amina@acme.test',
    role_label: 'Employee',
    sequence: 1,
    status: 'signed',
    signed_at: '2026-09-03T09:00:00Z',
  }],
  events: [],
};

const handlers = {
  onRemind: vi.fn(),
  onResend: vi.fn(),
  onUpdateDeadline: vi.fn(),
  onCancel: vi.fn(),
};

describe('company seal detail integration', () => {
  it('mounts the placement editor for a pending company seal', () => {
    render(
      <SignatureRequestDetails
        {...handlers}
        request={{
          ...baseRequest,
          seal_status: 'pending',
          seal: {
            page_number: 2,
            x: 0.1,
            y: 0.15,
            width: 0.2,
            height: 0.15,
          },
        }}
      />,
    );

    expect(
      screen.getByTestId('seal-placement-editor'),
    ).toHaveTextContent(
      'Signed artifact: signed-artifact-1 | Seal page: 2',
    );
  });

  it('does not mount placement while signatures are incomplete', () => {
    render(
      <SignatureRequestDetails
        {...handlers}
        request={{
          ...baseRequest,
          status: 'in_progress',
          signed_count: 0,
          seal_status: 'awaiting_signatures',
        }}
      />,
    );

    expect(
      screen.queryByTestId('seal-placement-editor'),
    ).not.toBeInTheDocument();
  });

  it('does not mount placement after the seal is applied', () => {
    render(
      <SignatureRequestDetails
        {...handlers}
        request={{
          ...baseRequest,
          seal_status: 'applied',
          sealed_at: '2026-09-03T09:30:00Z',
        }}
      />,
    );

    expect(
      screen.queryByTestId('seal-placement-editor'),
    ).not.toBeInTheDocument();
  });
});
