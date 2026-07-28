import {
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import SignatureEvidencePanel from '../components/documents/SignatureEvidencePanel.jsx';

vi.mock('../api/signatureApi', () => ({
  signatureApi: {
    artifactDownloadUrl: (
      requestId,
      artifactId,
    ) => `/api/signature-requests/${requestId}`
      + `/artifacts/${artifactId}/download`,
  },
}));

describe('SignatureEvidencePanel', () => {
  it('shows verified evidence and artifact downloads', () => {
    render(
      <SignatureEvidencePanel
        requestId="request-1"
        evidence={{
          evidence_status: 'verified',
          evidence_attempts: 1,
          evidence_completed_at: '2026-07-28T20:00:00',
          provider: 'dropbox_sign',
          artifacts: [{
            id: 'artifact-1',
            artifact_type: 'signed_document',
            checksum_sha256: 'a'.repeat(64),
          }],
        }}
        onRetry={vi.fn()}
      />,
    );

    expect(
      screen.getByText('Signed-file evidence package'),
    ).toBeInTheDocument();
    expect(screen.getByText('verified')).toBeInTheDocument();
    expect(
      screen.getByText('Final signed PDF'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Download' }),
    ).toHaveAttribute(
      'href',
      '/api/signature-requests/request-1'
      + '/artifacts/artifact-1/download',
    );
  });

  it('allows an administrator to retry failed evidence', () => {
    const onRetry = vi.fn();

    render(
      <SignatureEvidencePanel
        requestId="request-2"
        evidence={{
          evidence_status: 'failed',
          evidence_attempts: 8,
          evidence_last_error: 'Provider unavailable',
          provider: 'dropbox_sign',
          artifacts: [],
        }}
        onRetry={onRetry}
      />,
    );

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Retry evidence',
      }),
    );

    expect(onRetry).toHaveBeenCalledWith('request-2');
  });
});
