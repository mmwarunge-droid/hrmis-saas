from marshmallow import Schema, fields, validate, validates_schema, ValidationError


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
    def validate_recipient_deadlines(self, data, **kwargs):
        request_due_at = data.get('due_at')

        for recipient in data.get('recipients', []):
            recipient_due_at = recipient.get('due_at')

            if (
                recipient_due_at
                and request_due_at
                and recipient_due_at > request_due_at
            ):
                raise ValidationError({
                    'recipients': [
                        'Recipient deadlines cannot be later than '
                        'the request deadline.',
                    ],
                })


class SignatureDeclineSchema(Schema):
    reason = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=2000),
    )


class SignatureDeadlineUpdateSchema(Schema):
    due_at = fields.DateTime(required=True)


class SignatureCancelSchema(Schema):
    reason = fields.Str(
        required=False,
        load_default='Cancelled by an administrator',
        validate=validate.Length(min=2, max=2000),
    )
