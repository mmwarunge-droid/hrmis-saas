import {
  describe,
  expect,
  it,
} from 'vitest';

import {
  editableSigningField,
  isSigningFieldReady,
  signingFieldSubmission,
} from '../utils/signingFields.js';


const checkbox = {
  id: 'checkbox-1',
  field_type: 'checkbox',
  mark_style: 'either',
  required: true,
  value: null,
};


describe('signing checkbox fields', () => {
  it('treats checkbox fields as signer-editable', () => {
    expect(
      editableSigningField(checkbox),
    ).toBe(true);
  });

  it('requires an allowed mark before a required checkbox is ready', () => {
    expect(
      isSigningFieldReady(
        checkbox,
        {},
      ),
    ).toBe(false);

    expect(
      isSigningFieldReady(
        checkbox,
        {
          'checkbox-1': 'tick',
        },
      ),
    ).toBe(true);

    expect(
      isSigningFieldReady(
        checkbox,
        {
          'checkbox-1': 'cross',
        },
      ),
    ).toBe(true);

    expect(
      isSigningFieldReady(
        checkbox,
        {
          'checkbox-1': 'yes',
        },
      ),
    ).toBe(false);
  });

  it('submits the canonical checkbox mark', () => {
    expect(
      signingFieldSubmission(
        [checkbox],
        {
          'checkbox-1': 'cross',
        },
      ),
    ).toEqual([
      {
        field_id: 'checkbox-1',
        value: 'cross',
      },
    ]);
  });
});
