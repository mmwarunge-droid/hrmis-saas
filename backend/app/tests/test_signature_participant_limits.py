from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from marshmallow import ValidationError

from app.schemas.signature_schema import SignatureRequestCreateSchema


def request_payload(recipient_count):
    return {
        'document_id': str(uuid4()),
        'subject': 'Multi-party signing governance',
        'signing_mode': 'parallel',
        'assurance_level': 'standard',
        'due_at': (
            datetime.utcnow()
            + timedelta(days=7)
        ).replace(
            microsecond=0,
        ).isoformat(),
        'recipients': [
            {
                'employee_id': str(uuid4()),
                'role_label': f'Signatory {index + 1}',
                'sequence': 1,
            }
            for index in range(recipient_count)
        ],
    }


def test_standard_signature_request_rejects_more_than_four_signatories():
    with pytest.raises(ValidationError) as exc_info:
        SignatureRequestCreateSchema().load(
            request_payload(5),
        )

    assert 'recipients' in exc_info.value.messages


def test_standard_signature_request_accepts_four_signatories():
    result = SignatureRequestCreateSchema().load(
        request_payload(4),
    )

    assert len(result['recipients']) == 4
