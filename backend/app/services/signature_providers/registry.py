from flask import current_app

from app.services.signature_providers.base import (
    SignatureProviderNotConfigured,
)
from app.services.signature_providers.dropbox_sign import (
    DropboxSignProvider,
)


def get_signature_provider(name=None):
    provider_name = (
        name
        or current_app.config.get('SIGNATURE_PROVIDER')
        or 'internal'
    ).strip().lower()

    if provider_name == 'dropbox_sign':
        return DropboxSignProvider(
            api_key=current_app.config.get(
                'DROPBOX_SIGN_API_KEY',
            ),
            client_id=current_app.config.get(
                'DROPBOX_SIGN_CLIENT_ID',
            ),
            test_mode=current_app.config.get(
                'DROPBOX_SIGN_TEST_MODE',
                True,
            ),
        )

    raise SignatureProviderNotConfigured(
        f'Unsupported signature provider: {provider_name}',
    )
