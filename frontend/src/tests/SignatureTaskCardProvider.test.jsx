import {
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import {
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import SignatureTaskCard from '../components/documents/SignatureTaskCard.jsx';

const baseTask = {
  id: 'recipient-1',
  subject: 'Sign employment contract',
  message: 'Review before signing.',
  status: 'notified',
  due_at: '2026-08-10T17:00:00',
  document: {
    id: 'document-1',
    title: 'Employment contract',
  },
};

describe('SignatureTaskCard', () => {
  it('directs QES tasks to the provider-hosted ceremony', () => {
    const onViewed = vi.fn();
    const onSign = vi.fn();
    const onDecline = vi.fn();

    render(
      <SignatureTaskCard
        task={{
          ...baseTask,
          external_signing_required: true,
          provider: 'dropbox_sign',
          provider_status: 'awaiting_signature',
          assurance_level: 'qes',
        }}
        onViewed={onViewed}
        onSign={onSign}
        onDecline={onDecline}
      />,
    );

    expect(screen.getByText('QES target')).toBeInTheDocument();
    expect(
      screen.getByText('Complete signing through Dropbox Sign'),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Confirm signature' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Decline' }),
    ).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('link', { name: 'Review source document' }),
    );

    expect(onViewed).not.toHaveBeenCalled();
    expect(onSign).not.toHaveBeenCalled();
    expect(onDecline).not.toHaveBeenCalled();
  });

  it('retains internal actions for standard Kinetic tasks', () => {
    const onViewed = vi.fn();
    const onSign = vi.fn();
    const onDecline = vi.fn();

    render(
      <SignatureTaskCard
        task={{
          ...baseTask,
          external_signing_required: false,
          provider: null,
          assurance_level: 'standard',
        }}
        onViewed={onViewed}
        onSign={onSign}
        onDecline={onDecline}
      />,
    );

    fireEvent.click(
      screen.getByRole('button', { name: 'Confirm signature' }),
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Decline' }),
    );
    fireEvent.change(
      screen.getByLabelText('Reason for declining'),
      { target: { value: 'Needs revision' } },
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Submit decline' }),
    );

    expect(onSign).toHaveBeenCalledWith('recipient-1');
    expect(onDecline).toHaveBeenCalledWith(
      'recipient-1',
      'Needs revision',
    );
  });
});
