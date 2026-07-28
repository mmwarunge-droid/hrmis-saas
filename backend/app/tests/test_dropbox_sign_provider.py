from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.signature_providers.base import (
    SignatureProviderError,
    SignatureProviderNotConfigured,
)
from app.services.signature_providers.dropbox_sign import (
    DropboxSignProvider,
)


class FakeApiException(Exception):
    pass


class FakeConfiguration:
    def __init__(self, username):
        self.username = username


class FakeApiClient:
    def __init__(self, configuration):
        self.configuration = configuration

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeModel:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeSignatureRequestApi:
    calls = []

    def __init__(self, api_client):
        self.api_client = api_client

    def signature_request_send(
        self,
        *,
        signature_request_send_request,
    ):
        self.calls.append((
            'send',
            signature_request_send_request,
        ))
        return SimpleNamespace(
            signature_request=SimpleNamespace(
                signature_request_id='provider-request-1',
                details_url='https://provider.test/details',
                signatures=[SimpleNamespace(
                    signature_id='provider-signature-1',
                    status_code='awaiting_signature',
                )],
            ),
        )

    def signature_request_remind(
        self,
        *,
        signature_request_id,
        signature_request_remind_request,
    ):
        self.calls.append((
            'remind',
            signature_request_id,
            signature_request_remind_request,
        ))

    def signature_request_cancel(
        self,
        *,
        signature_request_id,
    ):
        self.calls.append((
            'cancel',
            signature_request_id,
        ))


class FakeModels:
    SubSignatureRequestSigner = FakeModel
    SignatureRequestSendRequest = FakeModel
    SignatureRequestRemindRequest = FakeModel


class FakeApiNamespace:
    SignatureRequestApi = FakeSignatureRequestApi


def _sdk_loader():
    return (
        FakeApiClient,
        FakeApiException,
        FakeConfiguration,
        FakeApiNamespace,
        FakeModels,
    )


def _signature_request(tmp_path):
    source = tmp_path / 'contract.pdf'
    source.write_bytes(b'%PDF-1.7 source document')
    recipient = SimpleNamespace(
        name='Amina Otieno',
        email='amina@example.test',
        provider_recipient_id='provider-signature-1',
    )

    return SimpleNamespace(
        id='ace-request-1',
        tenant_id='tenant-1',
        assurance_level='qes',
        signing_mode='sequential',
        subject='Qualified employment contract',
        message='Review and sign using eID.',
        due_at=datetime.now(timezone.utc) + timedelta(days=7),
        provider_request_id='provider-request-1',
        document=SimpleNamespace(
            id='document-1',
            file_path=str(source),
            checksum_sha256='a' * 64,
        ),
        recipients=[recipient],
    )


def test_dropbox_sign_provider_builds_non_test_eid_request(
    tmp_path,
):
    FakeSignatureRequestApi.calls.clear()
    signature_request = _signature_request(tmp_path)
    provider = DropboxSignProvider(
        api_key='api-key',
        client_id='client-id',
        test_mode=False,
        sdk_loader=_sdk_loader,
    )

    result = provider.create_request(signature_request)

    assert result.provider_request_id == 'provider-request-1'
    assert result.recipient_ids == {
        'amina@example.test': 'provider-signature-1',
    }
    assert result.status == 'awaiting_signature'
    assert result.metadata['is_eid'] is True
    assert result.metadata['assurance_confirmed'] is False

    operation, request_model = FakeSignatureRequestApi.calls[0]
    assert operation == 'send'
    assert request_model.files == [
        b'%PDF-1.7 source document',
    ]
    assert request_model.is_eid is True
    assert request_model.test_mode is False
    assert request_model.client_id == 'client-id'
    assert len(request_model.signers) == 1
    assert request_model.signers[0].email_address == (
        'amina@example.test'
    )
    assert request_model.signers[0].order == 0
    assert request_model.metadata['ace_request_id'] == (
        'ace-request-1'
    )
    assert request_model.metadata['assurance_target'] == 'qes'

    expires_at = datetime.fromtimestamp(
        request_model.expires_at,
        tz=timezone.utc,
    )
    assert expires_at.minute == 0
    assert expires_at.second == 0


def test_dropbox_sign_provider_forwards_reminder_and_cancel(
    tmp_path,
):
    FakeSignatureRequestApi.calls.clear()
    signature_request = _signature_request(tmp_path)
    provider = DropboxSignProvider(
        api_key='api-key',
        client_id='client-id',
        test_mode=False,
        sdk_loader=_sdk_loader,
    )

    provider.send_reminder(signature_request)
    provider.cancel_request(signature_request)

    remind = FakeSignatureRequestApi.calls[0]
    assert remind[0] == 'remind'
    assert remind[1] == 'provider-request-1'
    assert remind[2].email_address == 'amina@example.test'
    assert remind[2].name == 'Amina Otieno'
    assert FakeSignatureRequestApi.calls[1] == (
        'cancel',
        'provider-request-1',
    )


def test_dropbox_sign_provider_rejects_qes_test_mode(
    tmp_path,
):
    provider = DropboxSignProvider(
        api_key='api-key',
        client_id='client-id',
        test_mode=True,
        sdk_loader=_sdk_loader,
    )

    with pytest.raises(
        SignatureProviderNotConfigured,
        match='cannot run.*test mode',
    ):
        provider.create_request(_signature_request(tmp_path))


def test_dropbox_sign_provider_disables_embedded_qes(
    tmp_path,
):
    provider = DropboxSignProvider(
        api_key='api-key',
        client_id='client-id',
        test_mode=False,
        sdk_loader=_sdk_loader,
    )
    signature_request = _signature_request(tmp_path)

    with pytest.raises(
        SignatureProviderError,
        match='provider-hosted invitation',
    ):
        provider.create_signing_session(
            signature_request,
            signature_request.recipients[0],
        )
