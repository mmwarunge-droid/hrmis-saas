import {
  buildSigningFieldValues,
  isSigningFieldReady,
  missingRequiredSigningFields,
  signingFieldSubmission,
} from '../utils/signingFields.js';

import {
  describe,
  expect,
  it,
} from 'vitest';

function field(
  id,
  fieldType,
  extra = {},
) {
  return {
    id,
    field_type: fieldType,
    required: true,
    is_current_recipient: true,
    completed_at: null,
    value: null,
    ...extra,
  };
}

describe('signing field values', () => {
  const task = {
    name: 'Jane Wanjiku Doe',
    email: 'jane@example.test',
    role_label: 'Employee',
    fields: [
      field('signature-1', 'signature'),
      field('date-1', 'date'),
      field('name-1', 'name'),
      field(
        'text-1',
        'text',
        {
          prefill_key: 'employee.email',
        },
      ),
      field(
        'initials-1',
        'initials',
        {
          prefill_key: 'employee.initials',
        },
      ),
    ],
  };

  it('builds safe profile prefills for editable fields', () => {
    expect(
      buildSigningFieldValues(task),
    ).toEqual({
      'text-1': 'jane@example.test',
      'initials-1': 'JWD',
    });
  });

  it('treats server-controlled fields as ready', () => {
    expect(
      isSigningFieldReady(
        task.fields[0],
        {},
      ),
    ).toBe(true);

    expect(
      isSigningFieldReady(
        task.fields[1],
        {},
      ),
    ).toBe(true);

    expect(
      isSigningFieldReady(
        task.fields[2],
        {},
      ),
    ).toBe(true);
  });

  it('identifies missing required editable values', () => {
    const values = {
      'text-1': '',
      'initials-1': 'JWD',
    };

    expect(
      missingRequiredSigningFields(
        task.fields,
        values,
      ).map((item) => item.id),
    ).toEqual([
      'text-1',
    ]);
  });

  it('submits only editable non-empty fields', () => {
    const values = {
      'text-1': ' Nairobi ',
      'initials-1': ' JWD ',
    };

    expect(
      signingFieldSubmission(
        task.fields,
        values,
      ),
    ).toEqual([
      {
        field_id: 'text-1',
        value: 'Nairobi',
      },
      {
        field_id: 'initials-1',
        value: 'JWD',
      },
    ]);
  });
});
