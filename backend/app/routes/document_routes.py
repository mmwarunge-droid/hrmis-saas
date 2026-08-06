from datetime import date, timedelta

from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError
from sqlalchemy import or_

from app.extensions import db
from app.models import Document
from app.schemas.document_schema import DocumentUpdateSchema, DocumentUploadSchema
from app.services.document_service import (
    accessible_document_query,
    can_access_document,
    create_document,
    update_document,
)
from app.utils.decorators import (
    permission_required,
    request_tenant_id,
    tenant_query,
)
from app.utils.file_storage import send_stored_file
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success

document_bp = Blueprint('documents', __name__, url_prefix='/documents')


def _base_document_query():
    return accessible_document_query(
        current_user,
        tenant_query(Document),
    ).filter(Document.deleted_at.is_(None))


def _apply_document_filters(query):
    employee_id = request.args.get('employee_id')
    if employee_id:
        query = query.filter(Document.employee_id == employee_id)

    document_type = request.args.get('document_type')
    if document_type:
        query = query.filter(Document.document_type == document_type)

    signature_status = request.args.get('signature_status')
    if signature_status:
        query = query.filter(
            Document.signature_status == signature_status,
        )

    status = request.args.get('status')
    if status:
        query = query.filter(Document.status == status)

    q = request.args.get('q')
    if q:
        like = f'%{q.strip().lower()}%'
        query = query.filter(or_(
            db.func.lower(Document.title).like(like),
            db.func.lower(Document.original_filename).like(like),
            db.func.lower(Document.document_type).like(like),
        ))

    return query


def _apply_document_sort(query):
    sort_key = request.args.get('sort', 'created_at')
    direction = request.args.get('direction', 'desc').lower()
    descending = direction != 'asc'
    column = {
        'created_at': Document.created_at,
        'title': Document.title,
        'document_type': Document.document_type,
        'signature_status': Document.signature_status,
        'status': Document.status,
        'size_bytes': Document.size_bytes,
        'expiry_date': Document.expiry_date,
    }.get(sort_key, Document.created_at)

    return query.order_by(
        column.desc() if descending else column.asc(),
        Document.id.asc(),
    )


@document_bp.get('')
@jwt_required()
@permission_required('document:read')
def list_documents():
    page, per_page = get_pagination()
    query = _apply_document_filters(_base_document_query())
    pagination = _apply_document_sort(query).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return success(paginated_response(pagination))


@document_bp.get('/summary')
@jwt_required()
@permission_required('document:read')
def document_summary():
    query = _base_document_query()
    today = date.today()
    expiry_limit = today + timedelta(days=30)

    total = query.count()
    awaiting_signature = query.filter(
        Document.signature_status == 'pending',
    ).count()
    signed = query.filter(Document.signature_status == 'signed').count()
    expiring_soon = query.filter(
        Document.status == 'active',
        Document.expiry_date >= today,
        Document.expiry_date <= expiry_limit,
    ).count()
    folder_rows = (
        query.with_entities(
            Document.document_type,
            db.func.count(Document.id),
        )
        .group_by(Document.document_type)
        .order_by(Document.document_type.asc())
        .all()
    )

    return success({
        'total': total,
        'awaiting_signature': awaiting_signature,
        'signed': signed,
        'expiring_soon': expiring_soon,
        'folders': [
            {'document_type': document_type, 'count': count}
            for document_type, count in folder_rows
        ],
    })


@document_bp.post('/upload')
@jwt_required()
@permission_required('document:upload')
def upload_document():
    try:
        payload = DocumentUploadSchema().load(request.form.to_dict())
        tenant_id = request_tenant_id(payload)
        if not tenant_id:
            return fail('TENANT_REQUIRED', 'tenant_id is required for document upload', 422)
        document = create_document(payload, request.files.get('file'), tenant_id)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except Exception as exc:
        db.session.rollback()
        return fail('DOCUMENT_UPLOAD_FAILED', str(exc), 400)
    return success(document.to_dict(), 'Document uploaded', 201)


@document_bp.get('/<document_id>')
@jwt_required()
@permission_required('document:read')
def get_document(document_id):
    document = tenant_query(Document).filter_by(id=document_id, deleted_at=None).first_or_404()
    if not can_access_document(current_user, document):
        return fail('FORBIDDEN', 'You cannot access this document', 403)
    return success(document.to_dict())


@document_bp.get('/<document_id>/download')
@jwt_required()
@permission_required('document:read')
def download_document(document_id):
    document = tenant_query(Document).filter_by(id=document_id, deleted_at=None).first_or_404()
    if not can_access_document(current_user, document):
        return fail('FORBIDDEN', 'You cannot download this document', 403)
    return send_stored_file(document.file_path, document.original_filename)


@document_bp.patch('/<document_id>')
@jwt_required()
@permission_required('document:approve')
def patch_document(document_id):
    document = tenant_query(Document).filter_by(id=document_id, deleted_at=None).first_or_404()
    try:
        payload = DocumentUpdateSchema().load(request.get_json() or {})
        document = update_document(document, payload)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    return success(document.to_dict(), 'Document updated')
