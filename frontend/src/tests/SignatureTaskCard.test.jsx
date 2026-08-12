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

const task = {
  id: 'recipient-1',
  subject: 'Please sign your employment contract',
  message: 'Review all clauses before signing.',
  status: 'notified',
  due_at: '2026-08-10T17:00:00Z',
  document: {
    id: 'document-1',
    title: 'Employment contract',
  },
};

describe('SignatureTaskCard', () => {
  it('routes document review and signing to the secure task ceremony', () => {
    const onViewed = vi.fn();

    render(
      <SignatureTaskCard
        task={task}
        onViewed={onViewed}
        onDecline={vi.fn()}
      />,
    );

    fireEvent.click(
      screen.getByRole('link', {
        name: 'Review document',
      }),
    );

    const signLink = screen.getByRole('link', { name: 'Review & sign' });
    expect(signLink).toHaveAttribute('href', '/signature-tasks/recipient-1');
    expect(onViewed).toHaveBeenCalledWith('recipient-1');
  });

  it('submits a decline reason', () => {
    const onDecline = vi.fn();

    render(
      <SignatureTaskCard
        task={task}
        onViewed={vi.fn()}
        onDecline={onDecline}
      />,
    );

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Decline',
      }),
    );

    fireEvent.change(
      screen.getByLabelText('Reason for declining'),
      {
        target: {
          value: 'The contract terms need correction.',
        },
      },
    );

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Submit decline',
      }),
    );

    expect(onDecline).toHaveBeenCalledWith(
      'recipient-1',
      'The contract terms need correction.',
    );
  });
});
