const EDITABLE_FIELD_TYPES = new Set([
  'text',
  'initials',
]);

const SERVER_CONTROLLED_FIELD_TYPES = new Set([
  'signature',
  'date',
  'name',
]);

function normalizedValue(value) {
  return String(value ?? '').trim();
}

function employeeInitials(name) {
  return String(name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 32);
}

export function editableSigningField(field) {
  return EDITABLE_FIELD_TYPES.has(
    field?.field_type,
  );
}

export function serverControlledSigningField(field) {
  return SERVER_CONTROLLED_FIELD_TYPES.has(
    field?.field_type,
  );
}

export function recipientSigningFields(task) {
  return (task?.fields || []).filter((field) => (
    field.is_current_recipient
    && !field.completed_at
  ));
}

export function signingFieldPrefill(
  field,
  task,
) {
  if (!field?.prefill_key) return '';

  switch (field.prefill_key) {
    case 'employee.full_name':
      return task?.name || '';

    case 'employee.email':
      return task?.email || '';

    case 'employee.initials':
      return employeeInitials(task?.name);

    case 'recipient.role_label':
      return task?.role_label || '';

    default:
      return '';
  }
}

export function buildSigningFieldValues(task) {
  const values = {};

  for (const field of recipientSigningFields(task)) {
    if (!editableSigningField(field)) {
      continue;
    }

    const initialValue = (
      field.value
      || signingFieldPrefill(field, task)
      || ''
    );

    values[String(field.id)] = initialValue;
  }

  return values;
}

export function isSigningFieldReady(
  field,
  values,
) {
  if (!field?.required) {
    return true;
  }

  if (serverControlledSigningField(field)) {
    return true;
  }

  if (!editableSigningField(field)) {
    return false;
  }

  return Boolean(
    normalizedValue(
      values?.[String(field.id)]
      ?? field.value,
    ),
  );
}

export function missingRequiredSigningFields(
  fields,
  values,
) {
  return (fields || []).filter((field) => (
    field.required
    && !isSigningFieldReady(field, values)
  ));
}

export function signingFieldSubmission(
  fields,
  values,
) {
  return (fields || [])
    .filter(editableSigningField)
    .map((field) => ({
      field_id: String(field.id),
      value: normalizedValue(
        values?.[String(field.id)]
        ?? field.value,
      ),
    }))
    .filter((item) => item.value);
}
