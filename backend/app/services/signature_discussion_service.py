import re

from app.extensions import db
from app.models import (
    SignatureDiscussion,
    SignatureDiscussionComment,
    User,
)
from app.models.base import utcnow
from app.services.audit_service import log_event
from app.services.notification_service import create_notification
from app.services.signature_service import can_access_signature_request

MENTION_RE = re.compile(r'@([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})')


def _assert_access(actor, recipient):
    if not recipient or not can_access_signature_request(actor, recipient.signature_request):
        raise PermissionError('You cannot access this signature discussion')


def get_or_create_discussion(recipient, actor, *, commit=False):
    _assert_access(actor, recipient)
    discussion = SignatureDiscussion.query.filter_by(
        signature_request_id=recipient.signature_request_id,
        recipient_id=recipient.id,
        tenant_id=recipient.tenant_id,
    ).first()
    if discussion:
        return discussion
    discussion = SignatureDiscussion(
        tenant_id=recipient.tenant_id,
        signature_request_id=recipient.signature_request_id,
        recipient_id=recipient.id,
        status='open',
    )
    db.session.add(discussion)
    db.session.flush()
    if commit:
        db.session.commit()
    return discussion


def _mentioned_users(body, tenant_id):
    emails = {email.lower() for email in MENTION_RE.findall(body or '')}
    if not emails:
        return []
    return User.query.filter(
        User.tenant_id == tenant_id,
        db.func.lower(User.email).in_(emails),
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    ).all()


def add_comment(recipient, actor, body, *, commit=True, notify=True):
    _assert_access(actor, recipient)
    body = (body or '').strip()
    if len(body) < 2:
        raise ValueError('Discussion comments must contain at least 2 characters')
    if len(body) > 5000:
        raise ValueError('Discussion comments cannot exceed 5000 characters')

    discussion = get_or_create_discussion(recipient, actor)
    if discussion.status == 'resolved':
        discussion.status = 'open'
        discussion.resolved_at = None
        discussion.resolved_by_user_id = None

    mentioned = _mentioned_users(body, recipient.tenant_id)
    comment = SignatureDiscussionComment(
        tenant_id=recipient.tenant_id,
        discussion_id=discussion.id,
        author_user_id=actor.id,
        body=body,
        mentioned_user_ids_json=[str(user.id) for user in mentioned],
    )
    db.session.add(comment)
    db.session.flush()

    request = recipient.signature_request
    action_url = f'/signature-tasks/{recipient.id}'
    recipients = {str(user.id): user for user in mentioned}
    if request.created_by_id and str(request.created_by_id) != str(actor.id):
        admin = db.session.get(User, request.created_by_id)
        if admin:
            recipients[str(admin.id)] = admin
    if recipient.user_id and str(recipient.user_id) != str(actor.id):
        user = db.session.get(User, recipient.user_id)
        if user:
            recipients[str(user.id)] = user

    if notify:
        for user in recipients.values():
            create_notification(
                tenant_id=recipient.tenant_id,
                user_id=user.id,
                title=f'Document discussion: {request.subject}',
                body=f'{actor.full_name} added a comment that may need your attention.',
                notification_type='signature_discussion',
                priority='normal',
                action_url=action_url,
                metadata={
                    'signature_request_id': str(request.id),
                    'signature_recipient_id': str(recipient.id),
                    'discussion_id': str(discussion.id),
                    'comment_id': str(comment.id),
                },
            )

    log_event(
        'signature.discussion_comment',
        'SignatureDiscussion',
        discussion.id,
        tenant_id=recipient.tenant_id,
        metadata={'recipient_id': str(recipient.id)},
    )
    if commit:
        db.session.commit()
    return discussion, comment


def resolve_discussion(recipient, actor):
    _assert_access(actor, recipient)
    discussion = get_or_create_discussion(recipient, actor)
    discussion.status = 'resolved'
    discussion.resolved_at = utcnow()
    discussion.resolved_by_user_id = actor.id
    log_event(
        'signature.discussion_resolved',
        'SignatureDiscussion',
        discussion.id,
        tenant_id=recipient.tenant_id,
        metadata={'recipient_id': str(recipient.id)},
    )
    db.session.commit()
    return discussion
