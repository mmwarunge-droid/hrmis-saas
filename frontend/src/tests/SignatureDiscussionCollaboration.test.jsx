import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import {
  MemoryRouter,
  Route,
  Routes,
} from 'react-router-dom';

import { signatureApi } from '../api/signatureApi.js';
import SignatureDiscussionPanel from '../components/signatures/SignatureDiscussionPanel.jsx';
import useAuth from '../hooks/useAuth.js';
import SignatureDiscussion from '../pages/SignatureDiscussion.jsx';


vi.mock('../api/signatureApi.js', () => ({
  signatureApi: {
    discussion: vi.fn(),
    discussionMentions: vi.fn(),
    comment: vi.fn(),
    updateComment: vi.fn(),
    deleteComment: vi.fn(),
    resolveDiscussion: vi.fn(),

    // These deliberately exist so the standalone-page test can prove
    // that discussion-only collaborators never request signing data.
    recipient: vi.fn(),
    signingDocument: vi.fn(),
  },
}));

vi.mock('../hooks/useAuth.js', () => ({
  default: vi.fn(),
}));


function discussionPayload(overrides = {}) {
  return {
    id: 'discussion-1',
    signature_request_id: 'request-1',
    recipient_id: 'recipient-1',
    subject: 'Information Security Policy',
    signer_name: 'Signer Beta',
    status: 'open',
    resolved_at: null,
    comments: [],
    ...overrides,
  };
}


function comment({
  id,
  authorUserId,
  authorName,
  body,
  deleted = false,
  edited = false,
}) {
  return {
    id,
    discussion_id: 'discussion-1',
    author_user_id: authorUserId,
    author_name: authorName,
    body: deleted ? null : body,
    mentioned_user_ids: [],
    is_deleted: deleted,
    edited_at: edited
      ? '2026-08-19T06:00:00+00:00'
      : null,
    deleted_at: deleted
      ? '2026-08-19T06:10:00+00:00'
      : null,
    created_at: '2026-08-19T05:30:00+00:00',
  };
}


function renderPanel() {
  return render(
    <MemoryRouter>
      <SignatureDiscussionPanel
        recipientId="recipient-1"
        allowResolve
      />
    </MemoryRouter>,
  );
}


beforeEach(() => {
  vi.clearAllMocks();

  useAuth.mockReturnValue({
    user: {
      id: 'user-me',
      tenant_id: 'tenant-1',
      roles: ['EMPLOYEE'],
    },
  });

  signatureApi.discussion.mockResolvedValue({
    data: discussionPayload(),
  });

  signatureApi.discussionMentions.mockResolvedValue({
    data: [],
  });

  signatureApi.comment.mockResolvedValue({
    data: {},
  });

  signatureApi.updateComment.mockResolvedValue({
    data: {},
  });

  signatureApi.deleteComment.mockResolvedValue({
    data: {},
  });

  signatureApi.resolveDiscussion.mockResolvedValue({
    data: {},
  });
});


test(
  'selects an @mention and submits the explicit employee user UUID',
  async () => {
    signatureApi.discussionMentions.mockResolvedValue({
      data: [
        {
          user_id: 'user-alpha',
          employee_id: 'employee-alpha',
          full_name: 'Signer Alpha',
          job_title: 'Security Analyst',
        },
      ],
    });

    renderPanel();

    await screen.findByText('Discussion');

    const textarea = screen.getByLabelText(
      'Discussion comment',
    );

    fireEvent.change(textarea, {
      target: {
        value: 'Can @Sig',
      },
    });

    await waitFor(
      () => {
        expect(
          signatureApi.discussionMentions,
        ).toHaveBeenCalledWith(
          'recipient-1',
          'Sig',
        );
      },
      { timeout: 1500 },
    );

    expect(
      await screen.findByText('Signer Alpha'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Security Analyst'),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByText('Signer Alpha'),
    );

    expect(textarea.value).toBe(
      'Can @Signer Alpha ',
    );

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Reply',
      }),
    );

    await waitFor(() => {
      expect(
        signatureApi.comment,
      ).toHaveBeenCalledWith(
        'recipient-1',
        'Can @Signer Alpha',
        ['user-alpha'],
      );
    });
  },
);


test(
  'allows an author to edit and delete only their own comment',
  async () => {
    signatureApi.discussion.mockResolvedValue({
      data: discussionPayload({
        comments: [
          comment({
            id: 'mine',
            authorUserId: 'user-me',
            authorName: 'Current Employee',
            body: 'Original wording',
          }),
          comment({
            id: 'someone-else',
            authorUserId: 'other-user',
            authorName: 'Other Employee',
            body: 'Another employee comment',
          }),
        ],
      }),
    });

    const confirmSpy = vi
      .spyOn(window, 'confirm')
      .mockReturnValue(true);

    renderPanel();

    await screen.findByText('Original wording');

    const editButtons = screen.getAllByLabelText(
      'Edit comment',
    );
    const deleteButtons = screen.getAllByLabelText(
      'Delete comment',
    );

    // Only the current user's comment exposes author controls.
    expect(editButtons).toHaveLength(1);
    expect(deleteButtons).toHaveLength(1);

    fireEvent.click(editButtons[0]);

    const textarea = screen.getByLabelText(
      'Discussion comment',
    );

    expect(textarea.value).toBe(
      'Original wording',
    );

    fireEvent.change(textarea, {
      target: {
        value: 'Updated wording',
      },
    });

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Save changes',
      }),
    );

    await waitFor(() => {
      expect(
        signatureApi.updateComment,
      ).toHaveBeenCalledWith(
        'recipient-1',
        'mine',
        'Updated wording',
        [],
      );
    });

    fireEvent.click(
      screen.getByLabelText('Delete comment'),
    );

    expect(confirmSpy).toHaveBeenCalled();

    await waitFor(() => {
      expect(
        signatureApi.deleteComment,
      ).toHaveBeenCalledWith(
        'recipient-1',
        'mine',
      );
    });

    confirmSpy.mockRestore();
  },
);


test(
  'masks deleted comment contents while retaining visible thread history',
  async () => {
    signatureApi.discussion.mockResolvedValue({
      data: discussionPayload({
        comments: [
          comment({
            id: 'deleted-comment',
            authorUserId: 'user-me',
            authorName: 'Current Employee',
            body: 'Sensitive deleted wording',
            deleted: true,
          }),
          comment({
            id: 'edited-comment',
            authorUserId: 'other-user',
            authorName: 'Other Employee',
            body: 'Visible revised wording',
            edited: true,
          }),
        ],
      }),
    });

    renderPanel();

    expect(
      await screen.findByText(
        'This comment was deleted.',
      ),
    ).toBeInTheDocument();

    expect(
      screen.queryByText(
        'Sensitive deleted wording',
      ),
    ).not.toBeInTheDocument();

    expect(
      screen.getByText(
        'Visible revised wording',
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(/edited/),
    ).toBeInTheDocument();

    // A deleted comment cannot be edited or deleted again.
    expect(
      screen.queryByLabelText('Edit comment'),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByLabelText('Delete comment'),
    ).not.toBeInTheDocument();
  },
);


test(
  'discussion-only page never requests recipient or signing-document data',
  async () => {
    signatureApi.discussion.mockResolvedValue({
      data: discussionPayload({
        recipient_id: 'recipient-route',
        subject: 'Leave Policy Clarification',
      }),
    });

    render(
      <MemoryRouter
        initialEntries={[
          '/signature-discussions/recipient-route',
        ]}
      >
        <Routes>
          <Route
            path="/signature-discussions/:recipientId"
            element={<SignatureDiscussion />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole('heading', {
        name: 'Document discussion',
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /does not grant access to the underlying document/i,
      ),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        signatureApi.discussion,
      ).toHaveBeenCalledWith(
        'recipient-route',
      );
    });

    expect(
      signatureApi.recipient,
    ).not.toHaveBeenCalled();

    expect(
      signatureApi.signingDocument,
    ).not.toHaveBeenCalled();
  },
);
