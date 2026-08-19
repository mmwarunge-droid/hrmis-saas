
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Employee,
    SignatureDiscussion,
    SignatureDiscussionComment,
    SignatureDiscussionCommentRevision,
    SignatureDiscussionParticipant,
    User,
)
from app.models.base import utcnow
from app.services.audit_service import log_event
from app.services.notification_service import create_notification
from app.services.signature_service import can_access_signature_recipient



def _existing_discussion(recipient):
    return SignatureDiscussion.query.filter_by(
        signature_request_id=recipient.signature_request_id,
        recipient_id=recipient.id,
        tenant_id=recipient.tenant_id,
    ).first()


def _is_discussion_participant(actor, discussion):
    if not discussion:
        return False

    return SignatureDiscussionParticipant.query.filter_by(
        tenant_id=discussion.tenant_id,
        discussion_id=discussion.id,
        user_id=actor.id,
    ).first() is not None


def _assert_discussion_access(actor, recipient, discussion=None):
    if not recipient:
        raise PermissionError(
            'You cannot access this signature discussion'
        )

    if str(actor.tenant_id) != str(recipient.tenant_id):
        raise PermissionError(
            'You cannot access this signature discussion'
        )

    if can_access_signature_recipient(actor, recipient):
        return

    if discussion and _is_discussion_participant(actor, discussion):
        return

    raise PermissionError(
        'You cannot access this signature discussion'
    )


def _assert_recipient_access(actor, recipient):
    if not recipient or not can_access_signature_recipient(
        actor,
        recipient,
    ):
        raise PermissionError(
            'You cannot manage this signature discussion'
        )


def get_or_create_discussion(recipient, actor, *, commit=False):
    discussion = _existing_discussion(recipient)

    if discussion:
        _assert_discussion_access(
            actor,
            recipient,
            discussion,
        )
        return discussion

    # A mention-only collaborator can never create a discussion.
    _assert_recipient_access(actor, recipient)

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


def _explicit_mentioned_users(user_ids, tenant_id):
    normalized = {
        str(user_id)
        for user_id in (user_ids or [])
        if user_id
    }

    if not normalized:
        return []

    users = (
        User.query
        .join(
            Employee,
            db.and_(
                Employee.user_id == User.id,
                Employee.tenant_id == User.tenant_id,
            ),
        )
        .filter(
            User.tenant_id == tenant_id,
            User.id.in_(normalized),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            Employee.deleted_at.is_(None),
        )
        .all()
    )

    found = {str(user.id) for user in users}
    if found != normalized:
        raise ValueError(
            'One or more mentioned employees are unavailable.'
        )

    return users


def _ensure_participants(
    discussion,
    actor,
    users,
):
    existing_ids = {
        str(participant.user_id)
        for participant in discussion.participants
        if participant.user_id
    }

    added = []

    for user in users:
        user_id = str(user.id)

        if user_id == str(actor.id):
            continue

        if user_id in existing_ids:
            continue

        participant = SignatureDiscussionParticipant(
            tenant_id=discussion.tenant_id,
            discussion_id=discussion.id,
            user_id=user.id,
            added_by_user_id=actor.id,
            source='mention',
        )
        db.session.add(participant)
        added.append(user)
        existing_ids.add(user_id)

    if added:
        db.session.flush()

    return added


def _record_revision(
    comment,
    actor,
    revision_type,
):
    revision = SignatureDiscussionCommentRevision(
        tenant_id=comment.tenant_id,
        comment_id=comment.id,
        actor_user_id=actor.id,
        revision_type=revision_type,
        body=comment.body,
        mentioned_user_ids_json=list(
            comment.mentioned_user_ids_json or []
        ),
        occurred_at=utcnow(),
    )
    db.session.add(revision)
    db.session.flush()
    return revision


def _task_notification_users(recipient, actor):
    request = recipient.signature_request
    users = {}

    if (
        request.created_by_id
        and str(request.created_by_id) != str(actor.id)
    ):
        owner = db.session.get(
            User,
            request.created_by_id,
        )
        if owner:
            users[str(owner.id)] = owner

    if (
        recipient.user_id
        and str(recipient.user_id) != str(actor.id)
    ):
        signer = db.session.get(
            User,
            recipient.user_id,
        )
        if signer:
            users[str(signer.id)] = signer

    return users


def _discussion_participant_users(
    discussion,
    actor,
):
    users = {}

    for participant in discussion.participants:
        user = participant.user

        if not user:
            continue

        if str(user.id) == str(actor.id):
            continue

        if str(user.tenant_id) != str(discussion.tenant_id):
            continue

        if not user.is_active or user.deleted_at is not None:
            continue

        users[str(user.id)] = user

    return users


def _notify_comment(
    recipient,
    actor,
    discussion,
    comment,
    mentioned,
    *,
    notify_task_users=True,
    notify_participants=True,
):
    request = recipient.signature_request

    users = {}

    if notify_task_users:
        users.update(
            _task_notification_users(
                recipient,
                actor,
            )
        )

    if notify_participants:
        users.update(
            _discussion_participant_users(
                discussion,
                actor,
            )
        )

    mentioned_ids = {
        str(user.id)
        for user in mentioned
        if str(user.id) != str(actor.id)
    }

    for user in mentioned:
        if str(user.id) == str(actor.id):
            continue
        users[str(user.id)] = user

    for user_id, user in users.items():
        if str(user.id) == str(actor.id):
            continue

        if str(user.tenant_id) != str(recipient.tenant_id):
            continue

        if not user.is_active or user.deleted_at is not None:
            continue

        has_task_access = can_access_signature_recipient(
            user,
            recipient,
        )
        explicitly_mentioned = user_id in mentioned_ids

        if explicitly_mentioned:
            title = (
                f'You were mentioned: '
                f'{request.subject}'
            )
            body = (
                f'{actor.full_name} mentioned you '
                'in a document discussion.'
            )
        else:
            title = (
                f'Document discussion: '
                f'{request.subject}'
            )
            body = (
                f'{actor.full_name} added a comment '
                'that may need your attention.'
            )

        create_notification(
            tenant_id=recipient.tenant_id,
            user_id=user.id,
            title=title,
            body=body,
            notification_type='signature_discussion',
            priority='normal',
            action_url=(
                f'/signature-tasks/{recipient.id}'
                if has_task_access
                else f'/signature-discussions/{recipient.id}'
            ),
            metadata={
                'signature_request_id': str(request.id),
                'signature_recipient_id': str(recipient.id),
                'discussion_id': str(discussion.id),
                'comment_id': str(comment.id),
                'discussion_only': not has_task_access,
            },
        )


def _validate_body(body):
    body = (body or '').strip()

    if len(body) < 2:
        raise ValueError(
            'Discussion comments must contain at least 2 characters'
        )

    if len(body) > 5000:
        raise ValueError(
            'Discussion comments cannot exceed 5000 characters'
        )

    return body


def add_comment(
    recipient,
    actor,
    body,
    mentioned_user_ids=None,
    *,
    commit=True,
    notify=True,
):
    body = _validate_body(body)

    discussion = get_or_create_discussion(
        recipient,
        actor,
    )

    if discussion.status == 'resolved':
        discussion.status = 'open'
        discussion.resolved_at = None
        discussion.resolved_by_user_id = None

    mentioned = _explicit_mentioned_users(
        mentioned_user_ids or [],
        recipient.tenant_id,
    )

    comment = SignatureDiscussionComment(
        tenant_id=recipient.tenant_id,
        discussion_id=discussion.id,
        author_user_id=actor.id,
        body=body,
        mentioned_user_ids_json=[
            str(user.id)
            for user in mentioned
        ],
    )
    db.session.add(comment)
    db.session.flush()

    _ensure_participants(
        discussion,
        actor,
        mentioned,
    )
    _record_revision(
        comment,
        actor,
        'created',
    )

    if notify:
        _notify_comment(
            recipient,
            actor,
            discussion,
            comment,
            mentioned,
        )

    log_event(
        'signature.discussion_comment',
        'SignatureDiscussion',
        discussion.id,
        tenant_id=recipient.tenant_id,
        metadata={
            'recipient_id': str(recipient.id),
            'comment_id': str(comment.id),
        },
    )

    if commit:
        db.session.commit()

    return discussion, comment


def _comment_for_discussion(
    discussion,
    comment_id,
):
    comment = SignatureDiscussionComment.query.filter_by(
        id=comment_id,
        discussion_id=discussion.id,
        tenant_id=discussion.tenant_id,
    ).first()

    if not comment:
        raise LookupError(
            'Discussion comment was not found.'
        )

    return comment


def edit_comment(
    recipient,
    actor,
    comment_id,
    body,
    mentioned_user_ids=None,
    *,
    commit=True,
    notify=True,
):
    body = _validate_body(body)
    discussion = get_or_create_discussion(
        recipient,
        actor,
    )
    comment = _comment_for_discussion(
        discussion,
        comment_id,
    )

    if str(comment.author_user_id) != str(actor.id):
        raise PermissionError(
            'You can only edit your own discussion comments.'
        )

    if comment.deleted_at is not None:
        raise ValueError(
            'Deleted discussion comments cannot be edited.'
        )

    previous_mentions = set(
        comment.mentioned_user_ids_json or []
    )

    mentioned = _explicit_mentioned_users(
        mentioned_user_ids or [],
        recipient.tenant_id,
    )
    new_mentions = {
        str(user.id)
        for user in mentioned
    }

    if (
        body == comment.body
        and new_mentions == previous_mentions
    ):
        return discussion, comment

    comment.body = body
    comment.mentioned_user_ids_json = sorted(
        new_mentions
    )
    comment.edited_at = utcnow()

    _ensure_participants(
        discussion,
        actor,
        mentioned,
    )
    _record_revision(
        comment,
        actor,
        'edited',
    )

    newly_mentioned_ids = (
        new_mentions - previous_mentions
    )
    newly_mentioned = [
        user
        for user in mentioned
        if str(user.id) in newly_mentioned_ids
    ]

    if notify and newly_mentioned:
        _notify_comment(
            recipient,
            actor,
            discussion,
            comment,
            newly_mentioned,
            notify_task_users=False,
            notify_participants=False,
        )

    log_event(
        'signature.discussion_comment_edited',
        'SignatureDiscussion',
        discussion.id,
        tenant_id=recipient.tenant_id,
        metadata={
            'recipient_id': str(recipient.id),
            'comment_id': str(comment.id),
        },
    )

    if commit:
        db.session.commit()

    return discussion, comment


def delete_comment(
    recipient,
    actor,
    comment_id,
    *,
    commit=True,
):
    discussion = get_or_create_discussion(
        recipient,
        actor,
    )
    comment = _comment_for_discussion(
        discussion,
        comment_id,
    )

    if str(comment.author_user_id) != str(actor.id):
        raise PermissionError(
            'You can only delete your own discussion comments.'
        )

    if comment.deleted_at is not None:
        return discussion, comment

    # Keep body and mentions in persistent storage. to_dict() hides them
    # from the ordinary discussion UI once deleted.
    comment.deleted_at = utcnow()
    comment.deleted_by_user_id = actor.id

    _record_revision(
        comment,
        actor,
        'deleted',
    )

    log_event(
        'signature.discussion_comment_deleted',
        'SignatureDiscussion',
        discussion.id,
        tenant_id=recipient.tenant_id,
        metadata={
            'recipient_id': str(recipient.id),
            'comment_id': str(comment.id),
        },
    )

    if commit:
        db.session.commit()

    return discussion, comment


def mention_candidates(
    recipient,
    actor,
    query,
    *,
    limit=10,
):
    discussion = _existing_discussion(recipient)

    _assert_discussion_access(
        actor,
        recipient,
        discussion,
    )

    query = (query or '').strip().lower()
    if len(query) < 2:
        return []

    limit = max(1, min(int(limit or 10), 20))
    like = f'%{query}%'

    employees = (
        Employee.query
        .join(
            User,
            db.and_(
                Employee.user_id == User.id,
                Employee.tenant_id == User.tenant_id,
            ),
        )
        .filter(
            Employee.tenant_id == recipient.tenant_id,
            Employee.deleted_at.is_(None),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            User.id != actor.id,
            or_(
                db.func.lower(Employee.first_name).like(like),
                db.func.lower(Employee.last_name).like(like),
                db.func.lower(
                    Employee.first_name
                    + ' '
                    + Employee.last_name
                ).like(like),
                db.func.lower(Employee.job_title).like(like),
            ),
        )
        .order_by(
            Employee.first_name.asc(),
            Employee.last_name.asc(),
        )
        .limit(limit)
        .all()
    )

    return [
        {
            'user_id': str(employee.user_id),
            'employee_id': str(employee.id),
            'full_name': employee.full_name,
            'job_title': employee.job_title,
        }
        for employee in employees
        if employee.user_id
    ]


def resolve_discussion(recipient, actor):
    # Mention-only collaborators can participate, but they do not gain
    # authority to resolve the signer/owner discussion.
    _assert_recipient_access(actor, recipient)

    discussion = get_or_create_discussion(
        recipient,
        actor,
    )
    discussion.status = 'resolved'
    discussion.resolved_at = utcnow()
    discussion.resolved_by_user_id = actor.id

    log_event(
        'signature.discussion_resolved',
        'SignatureDiscussion',
        discussion.id,
        tenant_id=recipient.tenant_id,
        metadata={
            'recipient_id': str(recipient.id),
        },
    )

    db.session.commit()
    return discussion
