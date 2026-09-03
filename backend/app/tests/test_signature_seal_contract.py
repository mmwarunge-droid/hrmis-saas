import importlib.util

from sqlalchemy import CheckConstraint

from app.models import (
    SignatureArtifact,
    SignatureRequest,
)


def _check_constraint_sql(model):
    return [
        str(constraint.sqltext)
        for constraint in model.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    ]


def test_signature_request_exposes_company_seal_lifecycle():
    columns = SignatureRequest.__table__.columns

    assert 'seal_required' in columns
    assert 'seal_status' in columns

    status_constraints = ' '.join(
        _check_constraint_sql(SignatureRequest)
    )

    for status in (
        'not_required',
        'awaiting_signatures',
        'pending',
        'applied',
    ):
        assert status in status_constraints


def test_signature_artifacts_allow_immutable_sealed_document():
    artifact_constraints = ' '.join(
        _check_constraint_sql(SignatureArtifact)
    )

    assert 'sealed_document' in artifact_constraints


def test_company_seal_model_module_exists():
    assert importlib.util.find_spec(
        'app.models.signature_seal'
    ) is not None


def test_company_seal_service_module_exists():
    assert importlib.util.find_spec(
        'app.services.signature_seal_service'
    ) is not None
