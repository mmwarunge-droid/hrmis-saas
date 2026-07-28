from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class SignatureProviderError(RuntimeError):
    pass


class SignatureProviderNotConfigured(SignatureProviderError):
    pass


class InvalidProviderCallback(SignatureProviderError):
    pass


@dataclass(frozen=True)
class ProviderRequestResult:
    provider_request_id: str
    recipient_ids: dict[str, str]
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderSigningSession:
    sign_url: str
    expires_at: datetime | None = None


@dataclass(frozen=True)
class ProviderArtifactPayload:
    artifact_type: str
    filename: str
    content: bytes
    mime_type: str
    provider_artifact_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderCallback:
    event_id: str
    event_type: str
    event_time: datetime | None
    provider_request_id: str | None
    provider_recipient_id: str | None
    payload_sha256: str
    payload: dict[str, Any]


class SignatureProvider(ABC):
    provider_name: str

    @abstractmethod
    def create_request(self, signature_request) -> ProviderRequestResult:
        raise NotImplementedError

    @abstractmethod
    def create_signing_session(
        self,
        signature_request,
        recipient,
    ) -> ProviderSigningSession:
        raise NotImplementedError

    @abstractmethod
    def cancel_request(self, signature_request) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_reminder(self, signature_request) -> None:
        raise NotImplementedError

    @abstractmethod
    def download_artifacts(
        self,
        signature_request,
    ) -> list[ProviderArtifactPayload]:
        raise NotImplementedError

    @abstractmethod
    def parse_callback(self, raw_payload: str) -> ProviderCallback:
        raise NotImplementedError
