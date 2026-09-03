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
  due_at: '2099-08-20T17:00:00Z',
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
      due_at: '2099-08-20T17:00:00Z',
      signed_at: '2026-08-12T10:00:00Z',
    },
    {
      id: 'recipient-2',
      name: 'Brian Kimani',
      email: 'brian@acme.test',
      role_label: 'Manager',
      sequence: 2,
      status: 'notified',
      due_at: '2099-08-20T17:00:00Z',
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
        onResend={vi.fn()}
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
        onResend={vi.fn()}
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
  it('prefills and submits a terminal request resend', () => {
    const onResend = vi.fn();
    const expiredRequest = {
      ...request,
      status: 'expired',
      current_sequence: 1,
      due_at: '2026-08-20T17:00:00Z',
      signed_count: 0,
      recipients: request.recipients.map((recipient) => ({
        ...recipient,
        status: 'expired',
        signed_at: null,
      })),
    };

    render(
      <SignatureRequestDetails
        request={expiredRequest}
        onRemind={vi.fn()}
        onResend={onResend}
        onUpdateDeadline={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Resend for signature',
      }),
    );

    const message = screen.getByLabelText('Resend message');
    const resendForm = message.closest('form');

    expect(resendForm).not.toBeNull();
    expect(
      within(resendForm).getByText('Employment contract'),
    ).toBeInTheDocument();
    expect(
      within(resendForm).getByText(
        /Amina Otieno · amina@acme.test/,
      ),
    ).toBeInTheDocument();
    expect(
      within(resendForm).getByText(
        /Brian Kimani · brian@acme.test/,
      ),
    ).toBeInTheDocument();
    expect(message).toHaveValue(
      'We noticed that you have not yet signed this document. '
      + 'Please review it and complete your signature at your '
      + 'earliest convenience.',
    );

    fireEvent.change(
      screen.getByLabelText('New signing deadline'),
      { target: { value: '2026-09-15T17:00' } },
    );
    fireEvent.change(message, {
      target: {
        value: 'Please sign the replacement request.',
      },
    });

    fireEvent.click(
      screen.getAllByRole('button', {
        name: 'Resend for signature',
      }).at(-1),
    );

    expect(onResend).toHaveBeenCalledWith(
      'request-1',
      {
        due_at: new Date(
          '2026-09-15T17:00',
        ).toISOString(),
        message: 'Please sign the replacement request.',
      },
    );
  });

  it('offers resend immediately for an overdue internal request', () => {
    const overdueRequest = {
      ...request,
      due_at: '2020-08-20T17:00:00Z',
    };

    render(
      <SignatureRequestDetails
        request={overdueRequest}
        onRemind={vi.fn()}
        onResend={vi.fn()}
        onUpdateDeadline={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(
      screen.getByRole('button', {
        name: 'Resend for signature',
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', {
        name: 'Send reminder now',
      }),
    ).not.toBeInTheDocument();
  });

  it('does not show company seal controls when sealing is not required', () => {
    render(
      <SignatureRequestDetails
        request={request}
        onRemind={vi.fn()}
        onResend={vi.fn()}
        onUpdateDeadline={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(
      screen.queryByRole('heading', {
        name: 'Company seal',
      }),
    ).not.toBeInTheDocument();
  });

  it('shows a waiting seal state while signatures are incomplete', () => {
    const sealRequest = {
      ...request,
      seal_required: true,
      seal_status: 'awaiting_signatures',
    };

    render(
      <SignatureRequestDetails
        request={sealRequest}
        onRemind={vi.fn()}
        onResend={vi.fn()}
        onUpdateDeadline={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(
      screen.getByRole('heading', {
        name: 'Company seal',
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(/waiting for all signatories/i),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole('button', {
        name: /apply company seal/i,
      }),
    ).not.toBeInTheDocument();
  });

  it('shows a pending seal state after signing completes', () => {
    const completedRequest = {
      ...request,
      status: 'completed',
      current_sequence: 2,
      recipient_count: 2,
      signed_count: 2,
      seal_required: true,
      seal_status: 'pending',
      recipients: request.recipients.map((recipient) => ({
        ...recipient,
        status: 'signed',
        signed_at: recipient.signed_at
          || '2026-09-03T09:00:00Z',
      })),
    };

    render(
      <SignatureRequestDetails
        request={completedRequest}
        onRemind={vi.fn()}
        onResend={vi.fn()}
        onUpdateDeadline={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(
      screen.getByRole('heading', {
        name: 'Company seal',
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(/pending company seal/i),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /signing is complete.*seal/i,
      ),
    ).toBeInTheDocument();
  });

  it('shows an applied company seal as read only', () => {
    const appliedRequest = {
      ...request,
      status: 'completed',
      recipient_count: 2,
      signed_count: 2,
      seal_required: true,
      seal_status: 'applied',
      sealed_at: '2026-09-03T09:30:00Z',
      sealed_by_id: 'user-1',
    };

    render(
      <SignatureRequestDetails
        request={appliedRequest}
        onRemind={vi.fn()}
        onResend={vi.fn()}
        onUpdateDeadline={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    const heading = screen.getByRole('heading', {
      name: 'Company seal',
    });
    const sealSection = heading.closest('section');

    expect(sealSection).not.toBeNull();

    expect(
      within(sealSection).getByText(
        /company seal applied/i,
      ),
    ).toBeInTheDocument();

    expect(
      within(sealSection).getByText(/applied on/i),
    ).toBeInTheDocument();

    expect(
      within(sealSection).queryByRole('button', {
        name: /apply company seal/i,
      }),
    ).not.toBeInTheDocument();
  });

});
