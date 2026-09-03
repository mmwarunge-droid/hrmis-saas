import fs from 'node:fs';
import path from 'node:path';

import {
  describe,
  expect,
  it,
} from 'vitest';


function source(relativePath) {
  return fs.readFileSync(
    path.resolve(
      process.cwd(),
      relativePath,
    ),
    'utf8',
  );
}


const editor = source(
  'src/components/documents/'
  + 'SignatureFieldPlacement.jsx',
);

const task = source(
  'src/pages/SignatureTask.jsx',
);

const viewer = source(
  'src/components/documents/'
  + 'PdfSigningViewer.jsx',
);


describe('checkbox signing workspace', () => {
  it('offers checkbox placement and allowed-mark configuration', () => {
    expect(editor).toContain(
      "type: 'checkbox'",
    );
    expect(editor).toContain(
      'mark_style',
    );
    expect(editor).toContain(
      'Signer chooses tick or cross',
    );
  });

  it('provides checkbox interaction in the signer task', () => {
    expect(task).toContain(
      "field.field_type === 'checkbox'",
    );
    expect(task).toContain(
      'Tick',
    );
    expect(task).toContain(
      'Cross',
    );
  });

  it('renders checkbox semantics in the PDF overlay', () => {
    expect(viewer).toContain(
      "case 'checkbox'",
    );
    expect(viewer).toContain(
      "mark === 'tick'",
    );
    expect(viewer).toContain(
      "mark === 'cross'",
    );
  });
});
