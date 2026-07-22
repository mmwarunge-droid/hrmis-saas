from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError

from app.extensions import db
from app.models import Document
from app.schemas.document_schema import DocumentUpdateSchema, DocumentUploadSchema
from app.services.document_service import can_access_document, create_document, update_document
from app.utils.decorators import permission_required, tenant_query
from app.utils.file_storage import send_stored_file
from app.utils.pagination import get_pagination
from app.utils.response import fail, success

document_bp = Blueprint('documents', __name__, url_prefix='/documents')


@document_bp.get('')
@jwt_required()
@permission_required('document:read')
def list_documents():
    page, per_page = get_pagination()
    query = tenant_query(Document).filter(Document.deleted_at.is_(None))
    if request.args.get('employee_id'):
        query = query.filter(Document.employee_id == request.args['employee_id'])
    if request.args.get('document_type'):
        query = query.filter(Document.document_type == request.args['document_type'])
    q = request.args.get('q')
    if q:
        query = query.filter(db.func.lower(Document.title).like(f'%{q.lower()}%'))
    pagination = query.order_by(Document.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    items = [doc.to_dict() for doc in pagination.items if can_access_document(current_user, doc)]
    return success({'items': items, 'meta': {'page': pagination.page, 'per_page': pagination.per_page, 'total': pagination.total, 'pages': pagination.pages}})


@document_bp.post('/upload')
@jwt_required()
@permission_required('document:upload')
def upload_document():
    try:
        payload = DocumentUploadSchema().load(request.form.to_dict())
        tenant_id = payload.pop('tenant_id', None) if current_user.has_role('SUPER_ADMIN') else current_user.tenant_id
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
