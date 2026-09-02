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

describe('employee signing fields v2 contract', () => {
  const task = readSource(
    'src/pages/SignatureTask.jsx',
  );

  const viewer = readSource(
    'src/components/documents/PdfSigningViewer.jsx',
  );

  it('tracks recipient field values and required completion', () => {
    expect(task).toContain('fieldValues');
    expect(task).toContain('missingRequiredSigningFields');
    expect(task).toContain('buildSigningFieldValues');
  });

  it('submits recipient-owned field values with the signature', () => {
    expect(task).toContain(
      'fields: signingFieldSubmission(',
    );
  });

  it('provides interactive text and initials completion', () => {
    expect(task).toContain('editableSigningField(field)');
    expect(task).toContain('field.placeholder');
    expect(task).toContain('Previous incomplete field');
    expect(task).toContain('Next incomplete field');
  });

  it('links the field list to the PDF overlay', () => {
    expect(task).toContain('activeFieldId={activeFieldId}');
    expect(task).toContain('onFieldSelect={setActiveFieldId}');
  });

  it('makes PDF signing fields selectable', () => {
    expect(viewer).toContain('activeFieldId');
    expect(viewer).toContain('onFieldSelect');
    expect(viewer).toContain('signing-field-${field.id}');
    expect(viewer).not.toContain(
      'pointer-events-none absolute rounded-md',
    );
  });
});
