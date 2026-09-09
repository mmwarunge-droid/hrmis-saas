import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import SignatureTemplatePicker from '../components/documents/SignatureTemplatePicker.jsx';
import { signatureApi } from '../api/signatureApi.js';
vi.mock('../api/signatureApi.js', () => ({ signatureApi: { templates: vi.fn(), useTemplate: vi.fn() } }));

describe('Template selection', () => {
  it('loads templates and creates a review document for the selected employee', async () => {
    signatureApi.templates.mockResolvedValue({ data: { items: [{ id: 'template', name: 'Employment Contract - Kenya' }] } });
    signatureApi.useTemplate.mockResolvedValue({ data: { document: { id: 'new-copy' }, template: { id: 'template' } } });
    const onSelect = vi.fn();
    render(<SignatureTemplatePicker employees={[{ id: 'employee', full_name: 'Jane Doe' }]} tenants={[]} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Browse templates'));
    await screen.findByText('Employment Contract - Kenya');
    fireEvent.change(screen.getByLabelText('Signing template'), { target: { value: 'template' } });
    fireEvent.change(screen.getByLabelText('Template employee'), { target: { value: 'employee' } });
    fireEvent.click(screen.getByText('Review and assign signers'));
    await waitFor(() => expect(signatureApi.useTemplate).toHaveBeenCalledWith('template', 'employee', null));
    expect(onSelect).toHaveBeenCalledWith({ document: { id: 'new-copy' }, template: { id: 'template' } });
  });
});
