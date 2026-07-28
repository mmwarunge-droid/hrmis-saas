import io
import zipfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.signature_providers.base import (
    SignatureArtifactsNotReady,
)
from app.services.signature_providers.dropbox_sign import (
    DropboxSignProvider,
)


class FakeApiException(Exception):
    def __init__(self, status):
        super().__init__(f'HTTP {status}')
        self.status = status


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


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def read(self):
        return self.content


class FakeSignatureRequestApi:
    archive = None
    failure_status = None

    def __init__(self, _api_client):
        pass

    def signature_request_files(
        self,
        *,
        signature_request_id,
        file_type,
    ):
        assert signature_request_id == 'provider-request-1'
        assert file_type == 'zip'

        if self.failure_status:
            raise FakeApiException(self.failure_status)

        return FakeResponse(self.archive)


class FakeApiNamespace:
    SignatureRequestApi = FakeSignatureRequestApi


class FakeModels:
    pass


def _sdk_loader():
    return (
        FakeApiClient,
        FakeApiException,
        FakeConfiguration,
        FakeApiNamespace,
        FakeModels,
    )


def _signature_request():
    return SimpleNamespace(
        id='ace-request-1',
        tenant_id='tenant-1',
        assurance_level='qes',
        signing_mode='sequential',
        subject='Qualified employment contract',
        message='Sign using eID.',
        due_at=(
            datetime.now(timezone.utc)
            + timedelta(days=7)
        ),
        provider_request_id='provider-request-1',
        recipients=[SimpleNamespace(
            name='Amina Otieno',
            email='amina@example.test',
        )],
    )


def _archive():
    output = io.BytesIO()

    with zipfile.ZipFile(
        output,
        mode='w',
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            'Qualified employment contract.pdf',
            b'%PDF-1.7 final signed contract',
        )
        archive.writestr(
            'Audit Trail.pdf',
            b'%PDF-1.7 provider audit trail',
        )

    return output.getvalue()


def _provider():
    return DropboxSignProvider(
        api_key='api-key',
        client_id='client-id',
        test_mode=False,
        sdk_loader=_sdk_loader,
    )


def test_downloads_signed_pdf_and_audit_trail():
    FakeSignatureRequestApi.failure_status = None
    FakeSignatureRequestApi.archive = _archive()

    artifacts = _provider().download_artifacts(
        _signature_request(),
    )

    assert {
        artifact.artifact_type
        for artifact in artifacts
    } == {
        'signed_document',
        'audit_trail',
    }
    assert all(
        artifact.content.startswith(b'%PDF-')
        for artifact in artifacts
    )


def test_treats_http_409_as_not_ready():
    FakeSignatureRequestApi.failure_status = 409

    with pytest.raises(
        SignatureArtifactsNotReady,
        match='still preparing',
    ):
        _provider().download_artifacts(
            _signature_request(),
        )

    FakeSignatureRequestApi.failure_status = None
