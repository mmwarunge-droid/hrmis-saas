import {
  existsSync,
  readFileSync,
} from 'node:fs';
import { resolve } from 'node:path';

import {
  describe,
  expect,
  it,
} from 'vitest';

const editorPath = resolve(
  process.cwd(),
  'src/components/documents/SignatureSealPlacement.jsx',
);

const editor = existsSync(editorPath)
  ? readFileSync(editorPath, 'utf8')
  : '';

describe('company seal placement editor', () => {
  it('loads the immutable signed artifact for preview', () => {
    expect(editor).toContain('signed_document');
    expect(editor).toContain('signatureApi.artifact(');

    expect(editor).not.toContain('documentApi.content');
    expect(editor).not.toContain('signedDocument(');
    expect(editor).not.toContain('signedDocumentUrl');
  });

  it('sends authenticated PDF bytes directly to PDF.js', () => {
    expect(editor).toMatch(
      /new Uint8Array\(\s*await .*arrayBuffer\(\),?\s*\)/,
    );
    expect(editor).toMatch(/data:\s*pdfData/);

    expect(editor).not.toContain('URL.createObjectURL');
    expect(editor).not.toContain('URL.revokeObjectURL');
  });

  it('uploads only supported company seal image types', () => {
    expect(editor).toContain(
      'accept="image/png,image/jpeg,image/webp"',
    );
    expect(editor).toContain(
      'signatureApi.uploadSealImage(',
    );
    expect(editor).toContain('FileReader');
  });

  it('supports normalized move, resize and placement persistence', () => {
    expect(editor).toContain('onPointerMove');
    expect(editor).toContain("'resize'");
    expect(editor).toContain('page_number');
    expect(editor).toContain('width');
    expect(editor).toContain('height');
    expect(editor).toContain(
      'signatureApi.updateSealPlacement(',
    );
  });

  it('hydrates the persisted company seal image for reopened placement', () => {
    expect(editor).toContain(
      'signatureApi.sealImage(',
    );
    expect(editor).toContain(
      'response.data',
    );
    expect(editor).toContain(
      'readAsDataURL',
    );
  });

  it('supports page navigation on the signed PDF', () => {
    expect(editor).toContain(
      'aria-label="Previous PDF page"',
    );
    expect(editor).toContain(
      'aria-label="Next PDF page"',
    );
  });
});
