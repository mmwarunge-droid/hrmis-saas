import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.signature_providers.base import (
    InvalidProviderCallback,
    ProviderCallback,
    ProviderRequestResult,
    SignatureProvider,
    SignatureProviderError,
    SignatureProviderNotConfigured,
)


def _load_sdk():
    try:
        from dropbox_sign import (
            ApiClient,
            ApiException,
            Configuration,
            api,
            models,
        )
    except ImportError as exc:
        raise SignatureProviderNotConfigured(
            'The dropbox-sign package is not installed.',
        ) from exc

    return ApiClient, ApiException, Configuration, api, models


def _value(item, name, default=None):
    if item is None:
        return default
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _expiration_timestamp(value):
    if value.tzinfo is None:
        normalized = value.replace(tzinfo=timezone.utc)
    else:
        normalized = value.astimezone(timezone.utc)

    normalized = normalized.replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    now = datetime.now(timezone.utc)

    if not (
        now + timedelta(days=1)
        <= normalized
        <= now + timedelta(days=90)
    ):
        raise SignatureProviderError(
            'Dropbox Sign QES deadlines must be between '
            '1 and 90 days in the future.',
        )

    return int(normalized.timestamp())


class DropboxSignProvider(SignatureProvider):
    provider_name = 'dropbox_sign'

    def __init__(
        self,
        *,
        api_key,
        client_id,
        test_mode=True,
        sdk_loader=None,
    ):
        self.api_key = api_key
        self.client_id = client_id
        self.test_mode = bool(test_mode)
        self.sdk_loader = sdk_loader or _load_sdk

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

    def _require_qes(self, signature_request):
        self._require_credentials()

        if self.test_mode:
            raise SignatureProviderNotConfigured(
                'QES through eID cannot run in Dropbox Sign '
                'test mode. Set DROPBOX_SIGN_TEST_MODE=false '
                'only after the eID add-on is enabled.',
            )

        if signature_request.assurance_level != 'qes':
            raise SignatureProviderError(
                'Dropbox Sign eID is only enabled for QES '
                'requests.',
            )

        if len(signature_request.recipients) != 1:
            raise SignatureProviderError(
                'QES through eID requires exactly one signer.',
            )

        if signature_request.signing_mode != 'sequential':
            raise SignatureProviderError(
                'QES through eID requires sequential signing.',
            )

    def _api_context(self):
        (
            ApiClient,
            ApiException,
            Configuration,
            api,
            models,
        ) = self.sdk_loader()
        configuration = Configuration(username=self.api_key)
        return (
            ApiClient,
            ApiException,
            configuration,
            api,
            models,
        )

    def create_request(self, signature_request):
        self._require_qes(signature_request)

        document = signature_request.document
        recipient = signature_request.recipients[0]
        file_path = Path(document.file_path)

        if not file_path.is_file():
            raise SignatureProviderError(
                'The source document file is unavailable.',
            )

        (
            ApiClient,
            ApiException,
            configuration,
            api,
            models,
        ) = self._api_context()

        signer = models.SubSignatureRequestSigner(
            name=recipient.name,
            email_address=recipient.email,
            order=0,
        )
        metadata = {
            'ace_request_id': str(signature_request.id),
            'ace_document_id': str(document.id),
            'ace_tenant_id': str(signature_request.tenant_id),
            'assurance_target': 'qes',
            'source_sha256': document.checksum_sha256 or '',
        }

        try:
            with file_path.open('rb') as source_file:
                source_bytes = source_file.read()
                request_model = models.SignatureRequestSendRequest(
                    files=[source_bytes],
                    signers=[signer],
                    client_id=self.client_id,
                    title=signature_request.subject,
                    subject=signature_request.subject,
                    message=signature_request.message,
                    metadata=metadata,
                    allow_decline=True,
                    allow_reassign=False,
                    is_eid=True,
                    test_mode=False,
                    expires_at=_expiration_timestamp(
                        signature_request.due_at,
                    ),
                )

                with ApiClient(configuration) as api_client:
                    response = api.SignatureRequestApi(
                        api_client,
                    ).signature_request_send(
                        signature_request_send_request=(
                            request_model
                        ),
                    )
        except OSError as exc:
            raise SignatureProviderError(
                'The source document could not be read.',
            ) from exc
        except ApiException as exc:
            raise SignatureProviderError(
                'Dropbox Sign rejected the QES request.',
            ) from exc

        provider_request = _value(
            response,
            'signature_request',
        )
        provider_request_id = _value(
            provider_request,
            'signature_request_id',
        )
        signatures = _value(
            provider_request,
            'signatures',
            [],
        ) or []

        if not provider_request_id or len(signatures) != 1:
            raise SignatureProviderError(
                'Dropbox Sign returned an incomplete QES '
                'response.',
            )

        provider_signature = signatures[0]
        provider_recipient_id = _value(
            provider_signature,
            'signature_id',
        )
        provider_status = _value(
            provider_signature,
            'status_code',
            'awaiting_signature',
        )

        if not provider_recipient_id:
            raise SignatureProviderError(
                'Dropbox Sign did not return a signer ID.',
            )

        return ProviderRequestResult(
            provider_request_id=provider_request_id,
            recipient_ids={
                recipient.email.lower(): provider_recipient_id,
            },
            status=provider_status,
            metadata={
                'details_url': _value(
                    provider_request,
                    'details_url',
                ),
                'is_eid': True,
                'assurance_target': 'qes',
                'assurance_confirmed': False,
            },
        )

    def create_signing_session(
        self,
        signature_request,
        recipient,
    ):
        raise SignatureProviderError(
            'QES through eID uses the provider-hosted invitation '
            'sent by Dropbox Sign; embedded signing is disabled.',
        )

    def cancel_request(self, signature_request):
        self._require_qes(signature_request)

        if not signature_request.provider_request_id:
            raise SignatureProviderError(
                'The Dropbox Sign request ID is missing.',
            )

        (
            ApiClient,
            ApiException,
            configuration,
            api,
            _models,
        ) = self._api_context()

        try:
            with ApiClient(configuration) as api_client:
                api.SignatureRequestApi(
                    api_client,
                ).signature_request_cancel(
                    signature_request_id=(
                        signature_request.provider_request_id
                    ),
                )
        except ApiException as exc:
            raise SignatureProviderError(
                'Dropbox Sign could not queue cancellation.',
            ) from exc

    def send_reminder(self, signature_request):
        self._require_qes(signature_request)

        if not signature_request.provider_request_id:
            raise SignatureProviderError(
                'The Dropbox Sign request ID is missing.',
            )

        recipient = signature_request.recipients[0]
        (
            ApiClient,
            ApiException,
            configuration,
            api,
            models,
        ) = self._api_context()
        reminder = models.SignatureRequestRemindRequest(
            email_address=recipient.email,
            name=recipient.name,
        )

        try:
            with ApiClient(configuration) as api_client:
                api.SignatureRequestApi(
                    api_client,
                ).signature_request_remind(
                    signature_request_id=(
                        signature_request.provider_request_id
                    ),
                    signature_request_remind_request=reminder,
                )
        except ApiException as exc:
            raise SignatureProviderError(
                'Dropbox Sign could not send the reminder.',
            ) from exc

    def download_artifacts(self, signature_request):
        self._require_qes(signature_request)
        raise SignatureProviderError(
            'Dropbox Sign evidence download is activated in '
            'Phase 2C after the downloadable callback.',
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
