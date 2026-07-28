from flask import Blueprint, Response, request

from app.extensions import limiter
from app.services.signature_provider_service import (
    record_dropbox_sign_callback,
)
from app.services.signature_providers.base import (
    InvalidProviderCallback,
    SignatureProviderNotConfigured,
)
from app.utils.response import fail


signature_provider_bp = Blueprint(
    'signature_providers',
    __name__,
    url_prefix='/signature-providers',
)


@signature_provider_bp.post('/dropbox-sign/callback')
@limiter.exempt
def dropbox_sign_callback():
    raw_payload = request.form.get('json')

    if raw_payload is None:
        return fail(
            'INVALID_PROVIDER_CALLBACK',
            'The Dropbox Sign callback payload is missing.',
            400,
        )

    try:
        record_dropbox_sign_callback(raw_payload)
    except InvalidProviderCallback as exc:
        return fail(
            'INVALID_PROVIDER_CALLBACK',
            str(exc),
            401,
        )
    except SignatureProviderNotConfigured as exc:
        return fail(
            'SIGNATURE_PROVIDER_NOT_CONFIGURED',
            str(exc),
            503,
        )

    return Response(
        'Hello API Event Received',
        status=200,
        mimetype='text/plain',
    )
