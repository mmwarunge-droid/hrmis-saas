import hashlib

from flask_jwt_extended import current_user
from sqlalchemy import and_, false, or_, select

from app.extensions import db
from app.models import (
    Document,
    Employee,
    SignatureRecipient,
    SignatureRequest,
)
from app.services.audit_service import log_event
from app.utils.file_storage import save_document_file


DOCUMENT_ADMIN_ROLES = {
    'ORGANIZATION_OWNER',
    'HR_CONSULTANT',
    'CLIENT_ADMIN',
}
SIGNATURE_ACCESS_STATUSES = (
    'sent',
    'in_progress',
    'completed',
    'declined',
    'expired',
    'cancelled',
)
MANAGER_VISIBLE_ACCESS_LEVELS = ('employee', 'manager')


def _checksum(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def _signature_document_ids(user):
    """Return document IDs explicitly assigned to a signature recipient."""
    return (
        select(SignatureRequest.document_id)
        .join(
            SignatureRecipient,
            SignatureRecipient.signature_request_id
            == SignatureRequest.id,
        )
        .where(
            SignatureRecipient.user_id == user.id,
            SignatureRecipient.tenant_id == user.tenant_id,
            SignatureRequest.tenant_id == user.tenant_id,
            SignatureRequest.status.in_(SIGNATURE_ACCESS_STATUSES),
        )
    )


def accessible_document_query(user, query=None):
    """Apply document authorization before filtering, counting or pagination.

    Managers can see their own employee-visible documents, documents belonging
    to direct reports, unassigned manager-level shared documents, and documents
    explicitly assigned to them for signature. Employees can see only their own
    employee-level documents and assigned signature documents.
    """
    query = Document.query if query is None else query

    if not user:
        return query.filter(false())

    if user.has_role('SUPER_ADMIN'):
        return query

    if not user.tenant_id:
        return query.filter(false())

    query = query.filter(Document.tenant_id == user.tenant_id)

    if user.has_any_role(DOCUMENT_ADMIN_ROLES):
        return query

    access_clauses = [
        Document.id.in_(_signature_document_ids(user)),
    ]
    employee_profile = user.employee_profile

    if user.has_role('MANAGER'):
        access_clauses.append(
            and_(
                Document.employee_id.is_(None),
                Document.access_level == 'manager',
            )
        )

        if employee_profile:
            direct_report_ids = (
                select(Employee.id)
                .where(
                    Employee.tenant_id == user.tenant_id,
                    Employee.manager_id == employee_profile.id,
                    Employee.deleted_at.is_(None),
                )
            )
            access_clauses.extend([
                and_(
                    Document.employee_id == employee_profile.id,
                    Document.access_level.in_(
                        MANAGER_VISIBLE_ACCESS_LEVELS
                    ),
                ),
                and_(
                    Document.employee_id.in_(direct_report_ids),
                    Document.access_level.in_(
                        MANAGER_VISIBLE_ACCESS_LEVELS
                    ),
                ),
            ])

        return query.filter(or_(*access_clauses))

    if user.has_role('EMPLOYEE') and employee_profile:
        access_clauses.append(
            and_(
                Document.employee_id == employee_profile.id,
                Document.access_level == 'employee',
            )
        )

    return query.filter(or_(*access_clauses))


def can_access_document(user, document: Document) -> bool:
    if not user or not document:
        return False

    if user.has_role('SUPER_ADMIN'):
        return True

    if str(user.tenant_id) != str(document.tenant_id):
        return False

    if user.has_any_role(DOCUMENT_ADMIN_ROLES):
        return True

    return (
        accessible_document_query(user)
        .filter(Document.id == document.id)
        .with_entities(Document.id)
        .first()
        is not None
    )


def create_document(payload, file, tenant_id):
    employee_id = payload.get('employee_id')
    if employee_id and not Employee.query.filter_by(id=employee_id, tenant_id=tenant_id, deleted_at=None).first():
        raise ValueError('employee_id is invalid for this tenant')
    stored = save_document_file(file, tenant_id)
    checksum = _checksum(stored['file_path'])
    document = Document(
        tenant_id=tenant_id,
        uploaded_by_id=current_user.id,
        checksum_sha256=checksum,
        **payload,
        **stored,
    )
    db.session.add(document)
    db.session.flush()
    log_event('document.upload', 'Document', document.id, tenant_id=tenant_id, metadata={'filename': document.original_filename})
    db.session.commit()
    return document


def update_document(document, payload):
    for key, value in payload.items():
        setattr(document, key, value)
    log_event('document.update', 'Document', document.id, tenant_id=document.tenant_id)
    db.session.commit()
    return document
