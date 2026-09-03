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


class SignatureFieldCreateSchema(Schema):
    field_type = fields.Str(
        required=True,
        validate=validate.OneOf([
            'signature',
            'date',
            'text',
            'name',
            'initials',
            'checkbox',
        ]),
    )
    label = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=160),
    )
    placeholder = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=240),
    )
    prefill_key = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=80),
    )

    mark_style = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.OneOf([
            'tick',
            'cross',
            'either',
        ]),
    )
    page_number = fields.Int(
        required=True,
        validate=validate.Range(min=1, max=5000),
    )
    x = fields.Float(
        required=True,
        validate=validate.Range(min=0, max=1),
    )
    y = fields.Float(
        required=True,
        validate=validate.Range(min=0, max=1),
    )
    width = fields.Float(
        required=True,
        validate=validate.Range(min=0.01, max=1),
    )
    height = fields.Float(
        required=True,
        validate=validate.Range(min=0.01, max=1),
    )
    required = fields.Bool(required=False, load_default=True)

    @validates_schema
    def validate_page_bounds(self, data, **kwargs):
        field_type = data.get('field_type')
        mark_style = data.get('mark_style')

        if field_type == 'checkbox':
            data['mark_style'] = mark_style or 'tick'
        elif mark_style is not None:
            raise ValidationError({
                'mark_style': [
                    'Mark style is only valid for checkbox fields.',
                ],
            })
        if data.get('x', 0) + data.get('width', 0) > 1:
            raise ValidationError({
                'width': ['The field extends beyond the PDF page width.'],
            })
        if data.get('y', 0) + data.get('height', 0) > 1:
            raise ValidationError({
                'height': ['The field extends beyond the PDF page height.'],
            })


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
    fields = fields.List(
        fields.Nested(SignatureFieldCreateSchema),
        required=False,
        load_default=list,
        validate=validate.Length(max=20),
    )

    @validates_schema
    def validate_signing_fields(self, data, **kwargs):
        signing_fields = data.get('fields') or []
        if not signing_fields:
            return
        types = [
            field['field_type']
            for field in signing_fields
        ]

        if (
            'signature' not in types
            or 'date' not in types
        ):
            raise ValidationError({
                'fields': [
                    'Custom placement requires at least one '
                    'signature field and one date field.',
                ],
            })


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
    seal_required = fields.Bool(
        required=False,
        load_default=False,
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
        validate=validate.Length(min=1, max=4),
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


class SignatureSignSchema(Schema):
    signature_name = fields.Str(
        required=False,
        allow_none=True,
        load_default=None,
        validate=validate.Length(min=2, max=240),
    )


class SignatureFieldValueSchema(Schema):
    field_id = fields.UUID(required=True)
    value = fields.Str(
        required=False,
        allow_none=True,
        load_default=None,
        validate=validate.Length(max=2000),
    )


class SignatureSubmitSchema(Schema):
    consent = fields.Bool(required=True)
    signature_style = fields.Str(
        required=False,
        load_default='calligraphy_1',
        validate=validate.OneOf([
            'calligraphy_1',
            'calligraphy_2',
        ]),
    )
    fields = fields.List(
        fields.Nested(SignatureFieldValueSchema),
        required=False,
        load_default=list,
        validate=validate.Length(max=20),
    )

    @validates_schema
    def validate_submission(self, data, **kwargs):
        if data.get('consent') is not True:
            raise ValidationError({
                'consent': [
                    'You must consent to use the generated '
                    'electronic signature.',
                ],
            })

        field_ids = [
            str(item['field_id'])
            for item in data.get('fields') or []
        ]

        if len(field_ids) != len(set(field_ids)):
            raise ValidationError({
                'fields': [
                    'Each signing field may only be submitted once.',
                ],
            })


class SignatureDiscussionCommentSchema(Schema):
    body = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=5000),
    )
    mentioned_user_ids = fields.List(
        fields.UUID(),
        required=False,
        load_default=list,
    )


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


class SignatureResendSchema(Schema):
    due_at = fields.DateTime(required=True)
    message = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=5000),
    )

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
