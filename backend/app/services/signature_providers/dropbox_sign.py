import hashlib
import hmac
import json
from datetime import datetime, timezone

from app.services.signature_providers.base import (
    InvalidProviderCallback,
    ProviderCallback,
    SignatureProvider,
    SignatureProviderError,
    SignatureProviderNotConfigured,
)


class DropboxSignProvider(SignatureProvider):
    provider_name = 'dropbox_sign'

    def __init__(
        self,
        *,
        api_key,
        client_id,
        test_mode=True,
    ):
        self.api_key = api_key
        self.client_id = client_id
        self.test_mode = bool(test_mode)

    def _require_credentials(self):
        missing = []

        if not self.api_key:
            missing.append('DROPBOX_SIGN_API_KEY')

        if not self.client_id:
            missing.append('DROPBOX_SIGN_CLIENT_ID')

        if missing:
            raise SignatureProviderNotConfigured(
                'Missing Dropbox Sign configuration: '
                + ', '.join(missing),
            )

    def create_request(self, signature_request):
        self._require_credentials()
        raise SignatureProviderError(
            'Dropbox Sign request creation is not activated yet.',
        )

    def create_signing_session(
        self,
        signature_request,
        recipient,
    ):
        self._require_credentials()
        raise SignatureProviderError(
            'Dropbox Sign signing sessions are not activated yet.',
        )

    def cancel_request(self, signature_request):
        self._require_credentials()
        raise SignatureProviderError(
            'Dropbox Sign cancellation is not activated yet.',
        )

    def send_reminder(self, signature_request):
        self._require_credentials()
        raise SignatureProviderError(
            'Dropbox Sign reminders are not activated yet.',
        )

    def download_artifacts(self, signature_request):
        self._require_credentials()
        raise SignatureProviderError(
            'Dropbox Sign artifact download is not activated yet.',
        )

    def parse_callback(self, raw_payload):
        if not self.api_key:
            raise SignatureProviderNotConfigured(
                'DROPBOX_SIGN_API_KEY is required to verify callbacks.',
            )

        try:
            payload = json.loads(raw_payload)
            event = payload['event']
            event_time_raw = str(event['event_time'])
            event_type = str(event['event_type'])
            event_hash = str(event['event_hash'])
        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise InvalidProviderCallback(
                'Dropbox Sign callback payload is malformed.',
            ) from exc

        expected_hash = hmac.new(
            self.api_key.encode('utf-8'),
            f'{event_time_raw}{event_type}'.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_hash, event_hash):
            raise InvalidProviderCallback(
                'Dropbox Sign callback signature is invalid.',
            )

        try:
            event_time = datetime.fromtimestamp(
                int(event_time_raw),
                tz=timezone.utc,
            ).replace(tzinfo=None)
        except (TypeError, ValueError, OSError):
            event_time = None

        signature_request = payload.get('signature_request') or {}
        event_metadata = event.get('event_metadata') or {}

        provider_request_id = (
            signature_request.get('signature_request_id')
        )
        provider_recipient_id = (
            event_metadata.get('related_signature_id')
        )
        canonical_payload = json.dumps(
            payload,
            separators=(',', ':'),
            sort_keys=True,
        )
        payload_sha256 = hashlib.sha256(
            canonical_payload.encode('utf-8'),
        ).hexdigest()
        event_identity = ':'.join([
            event_hash,
            event_time_raw,
            event_type,
            provider_request_id or '',
            provider_recipient_id or '',
            payload_sha256,
        ])
        event_id = hashlib.sha256(
            event_identity.encode('utf-8'),
        ).hexdigest()

        return ProviderCallback(
            event_id=event_id,
            event_type=event_type,
            event_time=event_time,
            provider_request_id=provider_request_id,
            provider_recipient_id=provider_recipient_id,
            payload_sha256=payload_sha256,
            payload=payload,
        )
