from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from marshmallow import ValidationError

from app.schemas.signature_schema import (
    SignatureFieldCreateSchema,
    SignatureRecipientCreateSchema,
    SignatureSubmitSchema,
)
from app.services.native_signature_service import (
    NativeSignatureError,
    complete_recipient_fields,
)


def _field(
    field_type,
    *,
    required=True,
    label=None,
):
    return SimpleNamespace(
        id=uuid4(),
        field_type=field_type,
        value=None,
        required=required,
        label=label or field_type,
        completed_at=None,
    )


def _placement(field_type, **extra):
    return {
        'field_type': field_type,
        'page_number': 1,
        'x': 0.10,
        'y': 0.20,
        'width': 0.30,
        'height': 0.06,
        **extra,
    }


def test_signature_field_schema_supports_v2_types():
    schema = SignatureFieldCreateSchema()

    for field_type in (
        'signature',
        'date',
        'text',
        'name',
        'initials',
    ):
        loaded = schema.load(
            _placement(
                field_type,
                label='Employee field',
                placeholder='Complete this field',
                prefill_key='employee.full_name',
            )
        )

        assert loaded['field_type'] == field_type
        assert loaded['placeholder'] == 'Complete this field'
        assert loaded['prefill_key'] == 'employee.full_name'


def test_recipient_custom_fields_allow_extra_hr_fields():
    payload = {
        'employee_id': str(uuid4()),
        'fields': [
            _placement('signature'),
            _placement('date'),
            _placement('name'),
            _placement('text'),
            _placement('initials'),
        ],
    }

    loaded = SignatureRecipientCreateSchema().load(
        payload
    )

    assert [
        field['field_type']
        for field in loaded['fields']
    ] == [
        'signature',
        'date',
        'name',
        'text',
        'initials',
    ]


def test_custom_fields_still_require_signature_and_date():
    with pytest.raises(ValidationError):
        SignatureRecipientCreateSchema().load({
            'employee_id': str(uuid4()),
            'fields': [
                _placement('text'),
                _placement('name'),
            ],
        })


def test_submit_schema_accepts_recipient_field_values():
    field_id = uuid4()

    loaded = SignatureSubmitSchema().load({
        'consent': True,
        'signature_style': 'calligraphy_1',
        'fields': [
            {
                'field_id': str(field_id),
                'value': 'Nairobi, Kenya',
            },
        ],
    })

    assert str(
        loaded['fields'][0]['field_id']
    ) == str(field_id)

    assert (
        loaded['fields'][0]['value']
        == 'Nairobi, Kenya'
    )


def test_submit_schema_rejects_duplicate_field_ids():
    field_id = str(uuid4())

    with pytest.raises(ValidationError):
        SignatureSubmitSchema().load({
            'consent': True,
            'fields': [
                {
                    'field_id': field_id,
                    'value': 'First',
                },
                {
                    'field_id': field_id,
                    'value': 'Second',
                },
            ],
        })


def test_completion_uses_server_identity_and_submitted_text():
    signature = _field('signature')
    date = _field('date')
    name = _field('name')
    location = _field(
        'text',
        label='Location',
    )
    initials = _field('initials')

    recipient = SimpleNamespace(
        name='Jane Wanjiku Doe',
        fields=[
            signature,
            date,
            name,
            location,
            initials,
        ],
    )

    signed_at = datetime(
        2026,
        9,
        2,
        16,
        45,
    )

    complete_recipient_fields(
        recipient,
        signed_at,
        'Jane Wanjiku Doe',
        field_values=[
            {
                'field_id': str(location.id),
                'value': '  Nairobi, Kenya  ',
            },
            {
                'field_id': str(initials.id),
                'value': ' JWD ',
            },
        ],
    )

    assert signature.value == 'Jane Wanjiku Doe'
    assert date.value == '02 Sep 2026'
    assert name.value == 'Jane Wanjiku Doe'
    assert location.value == 'Nairobi, Kenya'
    assert initials.value == 'JWD'

    assert all(
        field.completed_at == signed_at
        for field in recipient.fields
    )


def test_completion_rejects_unknown_field_id():
    recipient = SimpleNamespace(
        name='Jane Doe',
        fields=[
            _field('signature'),
            _field('date'),
        ],
    )

    with pytest.raises(
        NativeSignatureError,
        match='do not belong',
    ):
        complete_recipient_fields(
            recipient,
            datetime(2026, 9, 2),
            'Jane Doe',
            field_values=[
                {
                    'field_id': str(uuid4()),
                    'value': 'tampered',
                },
            ],
        )


def test_completion_rejects_client_override_of_signature():
    signature = _field('signature')

    recipient = SimpleNamespace(
        name='Jane Doe',
        fields=[
            signature,
            _field('date'),
        ],
    )

    with pytest.raises(
        NativeSignatureError,
        match='server-controlled',
    ):
        complete_recipient_fields(
            recipient,
            datetime(2026, 9, 2),
            'Jane Doe',
            field_values=[
                {
                    'field_id': str(signature.id),
                    'value': 'Attacker Signature',
                },
            ],
        )


def test_completion_blocks_missing_required_text():
    recipient = SimpleNamespace(
        name='Jane Doe',
        fields=[
            _field('signature'),
            _field('date'),
            _field(
                'text',
                label='Work location',
            ),
        ],
    )

    with pytest.raises(
        NativeSignatureError,
        match='Work location',
    ):
        complete_recipient_fields(
            recipient,
            datetime(2026, 9, 2),
            'Jane Doe',
            field_values=[],
        )
