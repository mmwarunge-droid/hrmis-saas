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
import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import { documentApi } from '../api/documentApi.js';
import DocumentReview from '../pages/DocumentReview.jsx';

vi.mock('../api/documentApi.js', () => ({
  documentApi: {
    get: vi.fn(),
    content: vi.fn(),
    downloadUrl: vi.fn(),
  },
}));

function renderReview() {
  return render(
    <MemoryRouter initialEntries={['/documents/doc-123/review']}>
      <Routes>
        <Route
          path="/documents/:documentId/review"
          element={<DocumentReview />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('DocumentReview', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:document-preview'),
    });

    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });

    documentApi.get.mockResolvedValue({
      data: {
        id: 'doc-123',
        title: 'Board resolution',
      },
    });

    documentApi.downloadUrl.mockReturnValue(
      '/api/documents/doc-123/download',
    );
  });

  it('offers retry and download recovery when the preview fails', async () => {
    documentApi.content
      .mockRejectedValueOnce({
        error: {
          message: 'Preview service is unavailable.',
        },
      })
      .mockResolvedValueOnce({
        data: new Blob(['document'], { type: 'application/pdf' }),
      });

    renderReview();

    expect(
      await screen.findByRole('alert'),
    ).toHaveTextContent('Preview service is unavailable.');

    expect(
      screen.getByRole('link', { name: 'Download document' }),
    ).toHaveAttribute(
      'href',
      '/api/documents/doc-123/download',
    );

    fireEvent.click(
      screen.getByRole('button', { name: 'Try again' }),
    );

    await waitFor(() => {
      expect(documentApi.content).toHaveBeenCalledTimes(2);
    });

    expect(
      await screen.findByTitle('Board resolution'),
    ).toHaveAttribute('src', 'blob:document-preview');

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});