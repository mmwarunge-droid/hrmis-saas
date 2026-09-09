import { useRef, useState } from 'react';

export default function SignatureInput({ value, onChange, name }) {
  const canvas = useRef(null);
  const drawing = useRef(false);
  const [error, setError] = useState('');
  const mode = value.signature_input || 'generated';
  const select = (method) => { setError(''); onChange({ signature_input: method, signature_text: name || '', signature_image: null }); };
  const point = (event) => {
    const rect = canvas.current.getBoundingClientRect();
    return [(event.clientX - rect.left) * canvas.current.width / rect.width, (event.clientY - rect.top) * canvas.current.height / rect.height];
  };
  const upload = async (file) => {
    setError('');
    if (!file) return;
    if (file.type !== 'image/png' || file.size > 500000) { setError('Choose a PNG smaller than 500 KB.'); return; }
    const reader = new FileReader();
    reader.onload = () => onChange({ signature_input: 'uploaded', signature_image: reader.result });
    reader.onerror = () => setError('Unable to read image.');
    reader.readAsDataURL(file);
  };
  return <div className="mt-4 space-y-3">
    <label className="block text-sm">Signature method
      <select aria-label="Signature method" value={mode} onChange={(e) => select(e.target.value)} className="mt-1 w-full rounded border p-2">
        <option value="generated">Use profile signature</option><option value="typed">Type</option><option value="drawn">Draw</option><option value="uploaded">Upload PNG</option>
      </select>
    </label>
    {mode === 'typed' && <input aria-label="Typed signature" maxLength={240} value={value.signature_text || ''} onChange={(e) => onChange({ ...value, signature_text: e.target.value })} className="w-full rounded border p-3 font-serif italic" />}
    {mode === 'drawn' && <>
      <canvas ref={canvas} width={600} height={180} aria-label="Draw your signature" className="w-full touch-none rounded border bg-white"
        onPointerDown={(e) => { const ctx = canvas.current.getContext('2d'); drawing.current = true; canvas.current.setPointerCapture(e.pointerId); ctx.beginPath(); ctx.moveTo(...point(e)); ctx.lineWidth = 3; ctx.lineCap = 'round'; }}
        onPointerMove={(e) => { if (!drawing.current) return; const ctx = canvas.current.getContext('2d'); ctx.lineTo(...point(e)); ctx.stroke(); }}
        onPointerUp={() => { drawing.current = false; onChange({ signature_input: 'drawn', signature_image: canvas.current.toDataURL('image/png') }); }}
        onPointerCancel={() => { drawing.current = false; }} />
      <button type="button" onClick={() => { canvas.current.getContext('2d').clearRect(0, 0, 600, 180); onChange({ signature_input: 'drawn', signature_image: null }); }}>Clear drawing</button>
    </>}
    {mode === 'uploaded' && <input aria-label="Upload signature" type="file" accept="image/png" onChange={(e) => upload(e.target.files?.[0])} />}
    {mode === 'uploaded' && value.signature_image && <img src={value.signature_image} alt="Your signature preview" className="max-h-32" />}
    {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
  </div>;
}
