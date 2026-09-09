import json
import re
from uuid import UUID

from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import Schema, ValidationError, fields, validate
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.form_draft import FormDraft
from app.models.base import utcnow
from app.utils.response import fail, success

form_draft_bp = Blueprint('form_drafts', __name__, url_prefix='/form-drafts')
SENSITIVE_KEY = re.compile(r'password|secret|token|otp|recovery.?code|signature_image', re.I)


class DraftSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=220))
    revision = fields.Int(required=True, validate=validate.Range(min=0))
    data = fields.Dict(required=True)


def validate_data(value, depth=0):
    if depth > 20:
        raise ValueError('The draft contains too many nested sections.')
    if isinstance(value, dict):
        for key, child in value.items():
            if SENSITIVE_KEY.search(str(key)):
                raise ValueError('Passwords, tokens and signature images cannot be saved in drafts.')
            validate_data(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            validate_data(child, depth + 1)
    elif isinstance(value, str) and value.startswith('data:'):
        raise ValueError('Attachments cannot be saved in a form draft. Reattach them when resuming.')


def scoped_drafts():
    if request.args.get('owner_id') and request.args['owner_id'] != str(current_user.id):
        raise ValueError('The signed-in account changed. Return to the original account before accessing this draft.')
    tenant_id = current_user.tenant_id
    if current_user.has_role('SUPER_ADMIN'):
        try:
            tenant_id = UUID(request.args['tenant_id']) if request.args.get('tenant_id') else None
        except ValueError as exc:
            raise ValueError('Select a valid organization.') from exc
    scope = str(tenant_id) if tenant_id else 'global'
    return FormDraft.query.filter_by(owner_id=current_user.id, scope_key=scope), tenant_id, scope


@form_draft_bp.get('')
@jwt_required()
def list_drafts():
    try:
        query, _, _ = scoped_drafts()
        return success({'items': [draft.to_dict(False) for draft in query.order_by(FormDraft.updated_at.desc()).limit(100)]})
    except ValueError as exc:
        return fail('VALIDATION_ERROR', str(exc), 422)


@form_draft_bp.route('/<workflow_key>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required()
def form_draft(workflow_key):
    if not re.fullmatch(r'[\w:.-]{1,200}', workflow_key, flags=re.ASCII):
        return fail('VALIDATION_ERROR', 'Invalid draft identifier.', 422)
    try:
        query, tenant_id, scope = scoped_drafts()
        query = query.filter_by(workflow_key=workflow_key)
        draft = query.with_for_update().first()
        if request.method == 'GET':
            return success(draft.to_dict() if draft else None)
        if request.method == 'DELETE':
            if not draft:
                return success({}, 'Draft discarded')
            if request.args.get('revision', type=int) != draft.revision:
                return fail('DRAFT_CONFLICT', 'This draft changed in another tab. Reload it before discarding.', 409)
            db.session.delete(draft)
            db.session.commit()
            return success({}, 'Draft discarded')
        payload = DraftSchema().load(request.get_json() or {})
        validate_data(payload['data'])
        if len(json.dumps(payload['data'], allow_nan=False).encode()) > 131072:
            return fail('DRAFT_TOO_LARGE', 'The draft is too large. Attachments must be added when submitting.', 422)
        if payload['revision'] != (draft.revision if draft else 0):
            return fail('DRAFT_CONFLICT', 'This draft changed in another tab. Your current entries are intact; reload the saved draft before overwriting it.', 409)
        if draft:
            changed = query.filter_by(revision=payload['revision']).update({
                'title': payload['title'], 'data': payload['data'], 'revision': draft.revision + 1, 'updated_at': utcnow(),
            }, synchronize_session=False)
            if changed != 1:
                db.session.rollback()
                return fail('DRAFT_CONFLICT', 'The draft changed in another tab. Your entries are intact.', 409)
            db.session.refresh(draft)
        else:
            if FormDraft.query.filter_by(owner_id=current_user.id).count() >= 100:
                return fail('DRAFT_LIMIT', 'Discard an older draft before saving a new one.', 422)
            draft = FormDraft(owner_id=current_user.id, tenant_id=tenant_id, scope_key=scope,
                              workflow_key=workflow_key, title=payload['title'], data=payload['data'])
            db.session.add(draft)
        db.session.commit()
        return success(draft.to_dict(), 'Draft saved')
    except ValidationError as exc:
        db.session.rollback()
        return fail('VALIDATION_ERROR', exc.messages, 422)
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return fail('VALIDATION_ERROR', str(exc), 422)
    except IntegrityError:
        db.session.rollback()
        return fail('DRAFT_CONFLICT', 'Another tab saved this draft first. Your entries are intact.', 409)
