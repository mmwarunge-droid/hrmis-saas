import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import {
  describe,
  expect,
  it,
} from 'vitest';

const readSource = (relativePath) => readFileSync(
  resolve(process.cwd(), relativePath),
  'utf8',
);

describe('SIGN-EDITOR-V2 source contract', () => {
  const editor = readSource(
    'src/components/documents/SignatureFieldPlacement.jsx',
  );

  const form = readSource(
    'src/components/documents/SignatureRequestForm.jsx',
  );

  it('supports the five native signing field types', () => {
    for (const type of [
      'signature',
      'date',
      'name',
      'text',
      'initials',
    ]) {
      expect(editor).toContain(`type: '${type}'`);
    }
  });

  it('provides move, resize and individual deletion controls', () => {
    expect(editor).toContain('onPointerMove');
    expect(editor).toContain('resize');
    expect(editor).toContain(
      'aria-label="Delete selected field"',
    );

    expect(editor).not.toContain(
      '...current.filter((item) => item.field_type !== field.field_type)',
    );
  });

  it('provides field metadata controls', () => {
    expect(editor).toContain('aria-label="Field label"');
    expect(editor).toContain('aria-label="Field required"');
    expect(editor).toContain('aria-label="Field placeholder"');
    expect(editor).toContain('aria-label="Prefill source"');
  });

  it('provides page and zoom navigation', () => {
    expect(editor).toContain(
      'aria-label="Previous PDF page"',
    );
    expect(editor).toContain(
      'aria-label="Next PDF page"',
    );
    expect(editor).toContain('aria-label="Zoom in"');
    expect(editor).toContain('aria-label="Zoom out"');
    expect(editor).toContain('PageThumbnail');
  });

  it('makes direct PDF preparation the PDF default', () => {
    expect(form).toContain(
      "useState('document')",
    );

    expect(form).toContain(
      '&& isPdfDocument',
    );

    expect(form).toContain(
      'Prepare fields on PDF',
    );

    expect(form).not.toContain(
      'Recommended. Two signers appear side by side',
    );

    expect(form).not.toContain(
      'bg-whitepx-3',
    );
  });
});
