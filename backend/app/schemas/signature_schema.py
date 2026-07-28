from datetime import datetime, timedelta, timezone

from marshmallow import (
    Schema,
    ValidationError,
    fields,
    validate,
    validates_schema,
)


def _utc_naive(value):
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class SignatureRecipientCreateSchema(Schema):
    employee_id = fields.UUID(required=True)
    role_label = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=120),
    )
    sequence = fields.Int(
        required=False,
        load_default=1,
        validate=validate.Range(min=1),
    )
    due_at = fields.DateTime(required=False, allow_none=True)


class SignatureReminderCreateSchema(Schema):
    first_reminder_after_days = fields.Int(
        required=False,
        load_default=2,
        validate=validate.Range(min=0, max=365),
    )
    reminder_interval_days = fields.Int(
        required=False,
        load_default=2,
        validate=validate.Range(min=1, max=365),
    )
    escalation_days_before_due = fields.Int(
        required=False,
        allow_none=True,
        validate=validate.Range(min=0, max=365),
    )
    is_active = fields.Bool(
        required=False,
        load_default=True,
    )


class SignatureRequestCreateSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    document_id = fields.UUID(required=True)

    subject = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=220),
    )
    message = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=5000),
    )
    signing_mode = fields.Str(
        required=False,
        load_default='sequential',
        validate=validate.OneOf([
            'sequential',
            'parallel',
        ]),
    )
    assurance_level = fields.Str(
        required=False,
        load_default='standard',
        validate=validate.OneOf([
            'standard',
            'qes',
        ]),
    )
    due_at = fields.DateTime(required=True)

    recipients = fields.List(
        fields.Nested(SignatureRecipientCreateSchema),
        required=True,
        validate=validate.Length(min=1, max=50),
    )

    reminder = fields.Nested(
        SignatureReminderCreateSchema,
        required=False,
        load_default=dict,
    )

    @validates_schema
    def validate_workflow(self, data, **kwargs):
        request_due_at = data.get('due_at')

        normalized_due_at = (
            _utc_naive(request_due_at)
            if request_due_at
            else None
        )
        now = datetime.utcnow()

        if normalized_due_at and normalized_due_at <= now:
            raise ValidationError({
                'due_at': [
                    'The signature deadline must be in the future.',
                ],
            })

        recipients = data.get('recipients', [])

        for recipient in recipients:
            recipient_due_at = recipient.get('due_at')

            if (
                recipient_due_at
                and normalized_due_at
                and _utc_naive(recipient_due_at)
                > normalized_due_at
            ):
                raise ValidationError({
                    'recipients': [
                        'Recipient deadlines cannot be later than '
                        'the request deadline.',
                    ],
                })

        if data.get('assurance_level') == 'qes':
            errors = {}

            if len(recipients) != 1:
                errors['recipients'] = [
                    'QES through eID requires exactly one signer.',
                ]

            if data.get('signing_mode') != 'sequential':
                errors['signing_mode'] = [
                    'QES through eID requires sequential signing.',
                ]

            if normalized_due_at:
                provider_due_at = normalized_due_at.replace(
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                if not (
                    now + timedelta(days=1)
                    <= provider_due_at
                    <= now + timedelta(days=90)
                ):
                    errors['due_at'] = [
                        'Dropbox Sign QES deadlines must be between '
                        '1 and 90 days in the future.',
                    ]

            if errors:
                raise ValidationError(errors)


class SignatureDeclineSchema(Schema):
    reason = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=2000),
    )


class SignatureDeadlineUpdateSchema(Schema):
    due_at = fields.DateTime(required=True)

    @validates_schema
    def validate_due_at(self, data, **kwargs):
        due_at = data.get('due_at')

        if due_at and _utc_naive(due_at) <= datetime.utcnow():
            raise ValidationError({
                'due_at': [
                    'The signature deadline must be in the future.',
                ],
            })


class SignatureCancelSchema(Schema):
    reason = fields.Str(
        required=False,
        load_default='Cancelled by an administrator',
        validate=validate.Length(min=2, max=2000),
    )
