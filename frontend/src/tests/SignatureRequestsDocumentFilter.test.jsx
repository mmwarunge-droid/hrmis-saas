import {
  render,
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
    retryEvidence: vi.fn(),
  },
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
