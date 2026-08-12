from io import BytesIO

from flask import Blueprint, request, send_file
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError

from app.extensions import db
from app.models import (
    SignatureArtifact,
    SignatureRecipient,
    SignatureRequest,
)
from app.schemas.signature_schema import (
    SignatureCancelSchema,
    SignatureDeadlineUpdateSchema,
    SignatureDeclineSchema,
    SignatureDiscussionCommentSchema,
    SignatureSignSchema,
    SignatureRequestCreateSchema,
)
from app.services.signature_evidence_service import (
    SignatureEvidenceValidationError,
    artifact_content,
    retry_signature_evidence,
    serialize_signature_evidence,
)
from app.services.signature_providers.base import (
    SignatureProviderError,
    SignatureProviderNotConfigured,
)
from app.services.signature_service import (
    can_access_signature_recipient,
    can_access_signature_request,
    cancel_signature_request,
    create_signature_request,
    decline_signature,
    list_my_signature_tasks,
    list_signature_requests,
    mark_recipient_signed,
    mark_recipient_viewed,
    serialize_signature_request,
    send_signature_reminder,
    update_signature_deadline,
)
from app.utils.decorators import (
    active_tenant_id,
    permission_required,
    request_tenant_id,
    tenant_query,
)
from app.utils.response import fail, success


signature_bp = Blueprint(
    'signature_requests',
    __name__,
    url_prefix='/signature-requests',
)


def _provider_error(code, exc, status):
    db.session.rollback()
    return fail(code, str(exc), status)


def _recipient_for_active_tenant(recipient_id):
    return tenant_query(SignatureRecipient).filter_by(
        id=recipient_id,
    ).first_or_404()


@signature_bp.post('')
@jwt_required()
@permission_required('document:approve')
def create_request():
    try:
        payload = SignatureRequestCreateSchema().load(
            request.get_json() or {},
        )

        tenant_id = request_tenant_id(payload)

        if not tenant_id:
            return fail(
                'TENANT_REQUIRED',
                'tenant_id is required for signature requests',
                422,
            )

        signature_request = create_signature_request(
            payload,
            tenant_id,
            current_user,
        )
    except ValidationError as err:
        return fail(
            'VALIDATION_ERROR',
            err.messages,
            422,
        )
    except SignatureProviderNotConfigured as exc:
        return _provider_error(
            'SIGNATURE_PROVIDER_NOT_CONFIGURED',
            exc,
            503,
        )
    except SignatureProviderError as exc:
        return _provider_error(
            'SIGNATURE_PROVIDER_FAILED',
            exc,
            502,
        )
    except ValueError as exc:
        db.session.rollback()
        return fail(
            'SIGNATURE_REQUEST_FAILED',
            str(exc),
            400,
        )

    message = (
        'Qualified-signature request sent through Dropbox Sign'
        if signature_request.assurance_level == 'qes'
        else 'Signature request sent'
    )

    return success(
        serialize_signature_request(
            signature_request,
            include_events=True,
        ),
        message,
        201,
    )


@signature_bp.get('')
@jwt_required()
@permission_required('document:approve')
def requests():
    tenant_id = active_tenant_id()
    items = list_signature_requests(
        current_user,
        tenant_id=tenant_id,
        status=request.args.get('status'),
        document_id=request.args.get('document_id'),
    )

    return success({
        'items': [
            serialize_signature_request(item)
            for item in items
        ],
    })


@signature_bp.get('/my-tasks')
@jwt_required()
def my_tasks():
    return success({
        'items': list_my_signature_tasks(current_user),
    })


@signature_bp.get('/<request_id>')
@jwt_required()
def request_details(request_id):
    signature_request = tenant_query(SignatureRequest).filter_by(
        id=request_id,
    ).first_or_404()

    if not can_access_signature_request(
        current_user,
        signature_request,
    ):
        return fail(
            'FORBIDDEN',
            'You cannot access this signature request',
            403,
        )

    return success(
        serialize_signature_request(
            signature_request,
            include_events=True,
        ),
    )


@signature_bp.get('/recipients/<recipient_id>')
@jwt_required()
def recipient_details(recipient_id):
    recipient = _recipient_for_active_tenant(recipient_id)
    if not can_access_signature_recipient(current_user, recipient):
        return fail('FORBIDDEN', 'You cannot access this signature task', 403)
    signature_request = recipient.signature_request
    data = {
        **recipient.to_dict(),
        'subject': signature_request.subject,
        'message': signature_request.message,
        'request_status': signature_request.status,
        'provider': signature_request.provider,
        'provider_status': signature_request.provider_status,
        'assurance_level': signature_request.assurance_level,
        'external_signing_required': bool(
            signature_request.provider
            and signature_request.assurance_level == 'qes'
        ),
        'document': {
            'id': str(signature_request.document.id),
            'title': signature_request.document.title,
            'document_type': signature_request.document.document_type,
            'original_filename': signature_request.document.original_filename,
            'mime_type': signature_request.document.mime_type,
        },
    }
    return success(data)


@signature_bp.patch('/recipients/<recipient_id>/viewed')
@jwt_required()
def recipient_viewed(recipient_id):
    recipient = _recipient_for_active_tenant(recipient_id)

    try:
        recipient = mark_recipient_viewed(
            recipient,
            current_user,
        )
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except ValueError as exc:
        return fail(
            'SIGNATURE_ACTION_FAILED',
            str(exc),
            400,
        )

    return success(
        recipient.to_dict(),
        'Document view recorded',
    )


@signature_bp.patch('/recipients/<recipient_id>/sign')
@jwt_required()
def recipient_signed(recipient_id):
    recipient = _recipient_for_active_tenant(recipient_id)

    try:
        payload = SignatureSignSchema().load(request.get_json(silent=True) or {})
        recipient = mark_recipient_signed(
            recipient,
            current_user,
            payload['signature_name'],
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except ValueError as exc:
        return fail(
            'SIGNATURE_ACTION_FAILED',
            str(exc),
            400,
        )

    return success(
        recipient.to_dict(),
        'Signature recorded',
    )


@signature_bp.patch('/recipients/<recipient_id>/decline')
@jwt_required()
def recipient_declined(recipient_id):
    recipient = _recipient_for_active_tenant(recipient_id)

    try:
        payload = SignatureDeclineSchema().load(
            request.get_json() or {},
        )
        recipient = decline_signature(
            recipient,
            current_user,
            payload['reason'],
        )
    except ValidationError as err:
        return fail(
            'VALIDATION_ERROR',
            err.messages,
            422,
        )
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except ValueError as exc:
        return fail(
            'SIGNATURE_ACTION_FAILED',
            str(exc),
            400,
        )

    return success(
        recipient.to_dict(),
        'Signature request declined',
    )


@signature_bp.get('/recipients/<recipient_id>/discussion')
@jwt_required()
def recipient_discussion(recipient_id):
    from app.services.signature_discussion_service import get_or_create_discussion

    recipient = _recipient_for_active_tenant(recipient_id)
    try:
        discussion = get_or_create_discussion(recipient, current_user)
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    return success(discussion.to_dict())


@signature_bp.post('/recipients/<recipient_id>/discussion/comments')
@jwt_required()
def recipient_discussion_comment(recipient_id):
    from app.services.signature_discussion_service import add_comment

    recipient = _recipient_for_active_tenant(recipient_id)
    try:
        payload = SignatureDiscussionCommentSchema().load(request.get_json() or {})
        discussion, comment = add_comment(recipient, current_user, payload['body'])
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except ValueError as exc:
        return fail('DISCUSSION_COMMENT_FAILED', str(exc), 400)
    return success({'discussion': discussion.to_dict(), 'comment': comment.to_dict()}, 'Comment added', 201)


@signature_bp.patch('/recipients/<recipient_id>/discussion/resolve')
@jwt_required()
def recipient_discussion_resolve(recipient_id):
    from app.services.signature_discussion_service import resolve_discussion

    recipient = _recipient_for_active_tenant(recipient_id)
    try:
        discussion = resolve_discussion(recipient, current_user)
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    return success(discussion.to_dict(), 'Discussion resolved')


def _manageable_request(request_id):
    signature_request = tenant_query(SignatureRequest).filter_by(
        id=request_id,
    ).first_or_404()

    if not can_access_signature_request(
        current_user,
        signature_request,
    ):
        raise PermissionError(
            'You cannot manage this signature request.',
        )

    return signature_request


@signature_bp.get('/<request_id>/evidence')
@jwt_required()
@permission_required('document:approve')
def request_evidence(request_id):
    try:
        signature_request = _manageable_request(request_id)
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)

    return success(
        serialize_signature_evidence(signature_request),
    )


@signature_bp.post('/<request_id>/evidence/retry')
@jwt_required()
@permission_required('document:approve')
def retry_evidence(request_id):
    try:
        signature_request = _manageable_request(request_id)
        signature_request = retry_signature_evidence(
            signature_request,
            current_user,
        )
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except ValueError as exc:
        db.session.rollback()
        return fail(
            'SIGNATURE_EVIDENCE_RETRY_FAILED',
            str(exc),
            400,
        )

    return success(
        serialize_signature_evidence(signature_request),
        'Signature evidence retry queued',
    )


@signature_bp.get(
    '/<request_id>/artifacts/<artifact_id>/download',
)
@jwt_required()
@permission_required('document:approve')
def download_evidence_artifact(
    request_id,
    artifact_id,
):
    try:
        signature_request = _manageable_request(request_id)
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)

    artifact = SignatureArtifact.query.filter_by(
        id=artifact_id,
        signature_request_id=signature_request.id,
        tenant_id=signature_request.tenant_id,
    ).first_or_404()

    try:
        content = artifact_content(artifact)
    except (
        FileNotFoundError,
        SignatureEvidenceValidationError,
    ) as exc:
        return fail(
            'SIGNATURE_EVIDENCE_UNAVAILABLE',
            str(exc),
            409,
        )

    return send_file(
        BytesIO(content),
        mimetype=artifact.mime_type or (
            'application/octet-stream'
        ),
        as_attachment=True,
        download_name=artifact.original_filename,
        max_age=0,
    )


@signature_bp.post('/<request_id>/remind')
@jwt_required()
@permission_required('document:approve')
def remind_request(request_id):
    try:
        signature_request = _manageable_request(request_id)
        recipient_count = send_signature_reminder(
            signature_request,
            current_user,
        )
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except SignatureProviderNotConfigured as exc:
        return _provider_error(
            'SIGNATURE_PROVIDER_NOT_CONFIGURED',
            exc,
            503,
        )
    except SignatureProviderError as exc:
        return _provider_error(
            'SIGNATURE_PROVIDER_FAILED',
            exc,
            502,
        )
    except ValueError as exc:
        db.session.rollback()
        return fail(
            'SIGNATURE_REMINDER_FAILED',
            str(exc),
            400,
        )

    return success(
        {
            'request': serialize_signature_request(
                signature_request,
                include_events=True,
            ),
            'recipient_count': recipient_count,
        },
        'Signing reminder sent',
    )


@signature_bp.patch('/<request_id>/deadline')
@jwt_required()
@permission_required('document:approve')
def update_deadline(request_id):
    try:
        payload = SignatureDeadlineUpdateSchema().load(
            request.get_json() or {},
        )
        signature_request = _manageable_request(request_id)
        signature_request = update_signature_deadline(
            signature_request,
            payload['due_at'],
            current_user,
        )
    except ValidationError as err:
        return fail(
            'VALIDATION_ERROR',
            err.messages,
            422,
        )
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except SignatureProviderNotConfigured as exc:
        return _provider_error(
            'SIGNATURE_PROVIDER_NOT_CONFIGURED',
            exc,
            503,
        )
    except SignatureProviderError as exc:
        return _provider_error(
            'SIGNATURE_PROVIDER_FAILED',
            exc,
            502,
        )
    except ValueError as exc:
        db.session.rollback()
        return fail(
            'SIGNATURE_DEADLINE_UPDATE_FAILED',
            str(exc),
            400,
        )

    return success(
        serialize_signature_request(
            signature_request,
            include_events=True,
        ),
        'Signature deadline updated',
    )


@signature_bp.patch('/<request_id>/cancel')
@jwt_required()
@permission_required('document:approve')
def cancel_request(request_id):
    try:
        payload = SignatureCancelSchema().load(
            request.get_json() or {},
        )
        signature_request = _manageable_request(request_id)
        signature_request = cancel_signature_request(
            signature_request,
            current_user,
            payload['reason'],
        )
    except ValidationError as err:
        return fail(
            'VALIDATION_ERROR',
            err.messages,
            422,
        )
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except SignatureProviderNotConfigured as exc:
        return _provider_error(
            'SIGNATURE_PROVIDER_NOT_CONFIGURED',
            exc,
            503,
        )
    except SignatureProviderError as exc:
        return _provider_error(
            'SIGNATURE_PROVIDER_FAILED',
            exc,
            502,
        )
    except ValueError as exc:
        db.session.rollback()
        return fail(
            'SIGNATURE_CANCEL_FAILED',
            str(exc),
            400,
        )

    cancellation_pending = (
        signature_request.provider_status
        == 'cancellation_pending'
    )

    return success(
        serialize_signature_request(
            signature_request,
            include_events=True,
        ),
        (
            'Dropbox Sign cancellation requested'
            if cancellation_pending
            else 'Signature request cancelled'
        ),
    )
