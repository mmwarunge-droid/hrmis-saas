import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import SignatureTask from '../pages/SignatureTask.jsx';
import { signatureApi } from '../api/signatureApi.js';

vi.mock('../api/signatureApi.js', () => ({ signatureApi: {
  recipient: vi.fn(), signingDocument: vi.fn(), viewed: vi.fn(), submit: vi.fn(),
} }));
vi.mock('../components/documents/PdfSigningViewer.jsx', () => ({ default: () => <div>PDF ready</div> }));
vi.mock('../components/signatures/SignatureDiscussionPanel.jsx', () => ({ default: () => null }));
const task = {
  id: 'recipient', status: 'notified', request_status: 'sent', fields: [], signers: [],
  document: { id: 'document', title: 'Employment agreement' },
  signature_preview: 'J.Doe', recipient_count: 1, signed_count: 0,
};
function mount() {
  render(<MemoryRouter initialEntries={['/signature-tasks/recipient']}><Routes>
    <Route path="/signature-tasks/:recipientId" element={<SignatureTask />} />
  </Routes></MemoryRouter>);
}
beforeEach(() => {
  vi.clearAllMocks();
  signatureApi.recipient.mockResolvedValue({ data: task });
  signatureApi.signingDocument.mockResolvedValue({ arrayBuffer: async () => new ArrayBuffer(4) });
  signatureApi.viewed.mockResolvedValue({ data: { status: 'viewed' } });
});
it('shows an actionable task error and can retry loading', async () => {
  signatureApi.recipient.mockRejectedValueOnce({ error: { message: 'The task is unavailable.' } });
  mount();
  expect(await screen.findByText('The task is unavailable.')).toBeVisible();
  expect(screen.queryByText('Loading signing workspace…')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Retry loading task' }));
  expect(await screen.findByText('PDF ready')).toBeVisible();
});
it('replaces the PDF spinner with a retry action after failure', async () => {
  signatureApi.signingDocument.mockRejectedValueOnce({ error: { message: 'The source snapshot is unavailable.' } });
  mount();
  expect(await screen.findByText('The source snapshot is unavailable.')).toBeVisible();
  expect(screen.queryByText('Preparing document…')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Retry loading PDF' }));
  expect(await screen.findByText('PDF ready')).toBeVisible();
});
it('disables signing when the parent request was closed', async () => {
  signatureApi.recipient.mockResolvedValue({ data: { ...task, request_status: 'declined' } });
  mount();
  await screen.findByText('PDF ready');
  expect(screen.queryByRole('button', { name: /sign & submit/i })).not.toBeInTheDocument();
});
