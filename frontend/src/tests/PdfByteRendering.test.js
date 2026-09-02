import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, test } from 'vitest';

const readSource = (relativePath) => (
  readFileSync(
    resolve(process.cwd(), relativePath),
    'utf8',
  )
);

const signatureTask = readSource(
  'src/pages/SignatureTask.jsx',
);

const pdfViewer = readSource(
  'src/components/documents/PdfSigningViewer.jsx',
);

const fieldPlacement = readSource(
  'src/components/documents/SignatureFieldPlacement.jsx',
);

const vercelConfig = JSON.parse(
  readSource('vercel.json'),
);

describe('secure PDF byte rendering', () => {
  test('signing task does not create a blob URL for PDF.js', () => {
    expect(signatureTask).not.toContain(
      'URL.createObjectURL',
    );
    expect(signatureTask).not.toContain(
      'URL.revokeObjectURL',
    );

    expect(signatureTask).toMatch(
      /new Uint8Array\(\s*await blob\.arrayBuffer\(\),?\s*\)/,
    );
  });

  test('PDF viewer sends authenticated bytes directly to PDF.js', () => {
    expect(pdfViewer).not.toContain(
      'URL.createObjectURL',
    );

    expect(pdfViewer).toMatch(
      /data:\s*source/,
    );
  });

  test('admin field placement renders authenticated bytes directly', () => {
    expect(fieldPlacement).not.toContain(
      'URL.createObjectURL',
    );
    expect(fieldPlacement).not.toContain(
      'URL.revokeObjectURL',
    );

    expect(fieldPlacement).toMatch(
      /data:\s*pdfData/,
    );
  });

  test('CSP stays strict without blob in connect-src', () => {
    const catchAll = vercelConfig.headers.find(
      (entry) => entry.source === '/(.*)',
    );

    expect(catchAll).toBeTruthy();

    const cspHeader = catchAll.headers.find(
      (header) => (
        header.key === 'Content-Security-Policy'
      ),
    );

    expect(cspHeader).toBeTruthy();

    const connectDirective = cspHeader.value
      .split(';')
      .map((directive) => directive.trim())
      .find((directive) => (
        directive.startsWith('connect-src ')
      ));

    expect(connectDirective).toBe(
      "connect-src 'self' https:",
    );
    expect(connectDirective).not.toContain(
      'blob:',
    );
  });
});
