from marshmallow import ValidationError

ALLOWED_DOCUMENT_TYPES = {'contract', 'policy', 'tax', 'certification', 'id', 'other'}
LEAVE_STATUSES = {'pending', 'approved', 'rejected', 'cancelled'}
EMPLOYMENT_STATUSES = {'active', 'probation', 'suspended', 'terminated'}


def validate_choice(value, allowed, field_name='value'):
    if value not in allowed:
        raise ValidationError(f'{field_name} must be one of: {", ".join(sorted(allowed))}')
