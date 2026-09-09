import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import SignatureInput from '../components/documents/SignatureInput.jsx';

function Harness() {
  const [value, setValue] = useState({ signature_input: 'generated' });
  return <SignatureInput value={value} onChange={setValue} name="Jane Doe" />;
}

describe('Signature input', () => {
  it('allows typing a signature and clears the typed mark when switching methods', () => {
    render(<Harness />);
    fireEvent.change(screen.getByLabelText('Signature method'), { target: { value: 'typed' } });
    fireEvent.change(screen.getByLabelText('Typed signature'), { target: { value: 'Jane D.' } });
    expect(screen.getByLabelText('Typed signature')).toHaveValue('Jane D.');
    fireEvent.change(screen.getByLabelText('Signature method'), { target: { value: 'uploaded' } });
    expect(screen.queryByLabelText('Typed signature')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Upload signature')).toBeInTheDocument();
  });
  it('rejects a non-PNG upload before submission', () => {
    render(<Harness />);
    fireEvent.change(screen.getByLabelText('Signature method'), { target: { value: 'uploaded' } });
    fireEvent.change(screen.getByLabelText('Upload signature'), { target: { files: [new File(['<svg/>'], 'signature.svg', { type: 'image/svg+xml' })] } });
    expect(screen.getByRole('alert')).toHaveTextContent('Choose a PNG smaller than 500 KB.');
  });
});
