import {
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';
import {
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import SignatureRequestDetails from '../components/documents/SignatureRequestDetails.jsx';

const request = {
  id: 'request-1',
  subject: 'Employment contract approval',
  message: 'Review the contract before signing.',
  status: 'in_progress',
  signing_mode: 'sequential',
  current_sequence: 2,
  due_at: '2026-08-20T17:00:00Z',
  recipient_count: 2,
  signed_count: 1,
  document: {
    id: 'document-1',
    title: 'Employment contract',
  },
  recipients: [
    {
      id: 'recipient-1',
      name: 'Amina Otieno',
      email: 'amina@acme.test',
      role_label: 'Employee',
      sequence: 1,
      status: 'signed',
      due_at: '2026-08-20T17:00:00Z',
      signed_at: '2026-08-12T10:00:00Z',
    },
    {
      id: 'recipient-2',
      name: 'Brian Kimani',
      email: 'brian@acme.test',
      role_label: 'Manager',
      sequence: 2,
      status: 'notified',
      due_at: '2026-08-20T17:00:00Z',
      signed_at: null,
    },
  ],
  events: [
    {
      id: 'event-1',
      event_type: 'signature.recipient_signed',
      description: 'Amina Otieno signed the document',
      occurred_at: '2026-08-12T10:00:00Z',
    },
  ],
};

describe('SignatureRequestDetails', () => {
  it('renders workflow progress and current signatory', () => {
    render(
      <SignatureRequestDetails
        request={request}
        onRemind={vi.fn()}
        onUpdateDeadline={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(
      screen.getByText('1 of 2 signed'),
    ).toBeInTheDocument();

    const currentSignatoryCard = screen
      .getByText('Current signatory')
      .closest('section');

    expect(currentSignatoryCard).not.toBeNull();

    expect(
      within(currentSignatoryCard).getByText(
        'Brian Kimani',
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        'Amina Otieno signed the document',
      ),
    ).toBeInTheDocument();
  });

  it('submits reminder, deadline and cancellation actions', () => {
    const onRemind = vi.fn();
    const onUpdateDeadline = vi.fn();
    const onCancel = vi.fn();

    render(
      <SignatureRequestDetails
        request={request}
        onRemind={onRemind}
        onUpdateDeadline={onUpdateDeadline}
        onCancel={onCancel}
      />,
    );

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Send reminder now',
      }),
    );

    expect(onRemind).toHaveBeenCalledWith('request-1');

    fireEvent.change(
      screen.getByLabelText('New deadline'),
      {
        target: {
          value: '2026-08-25T17:00',
        },
      },
    );

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Update deadline',
      }),
    );

    expect(onUpdateDeadline).toHaveBeenCalledWith(
      'request-1',
      new Date('2026-08-25T17:00').toISOString(),
    );

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Cancel request',
      }),
    );

    fireEvent.change(
      screen.getByLabelText(
        'Reason for cancellation',
      ),
      {
        target: {
          value: 'The document requires revision.',
        },
      },
    );

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Confirm cancellation',
      }),
    );

    expect(onCancel).toHaveBeenCalledWith(
      'request-1',
      'The document requires revision.',
    );
  });
});
