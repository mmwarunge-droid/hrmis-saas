from collections.abc import Iterable

from app.extensions import db
from app.models import Notification, User
from app.models.base import utcnow

VALID_PRIORITIES = {'low', 'normal', 'high', 'urgent'}


def create_notification(
    *,
    tenant_id,
    user_id,
    title,
    body=None,
    notification_type='system',
    priority='normal',
    action_url=None,
    metadata=None,
    commit=False,
):
    if not tenant_id or not user_id:
        return None
    if priority not in VALID_PRIORITIES:
        raise ValueError('Unsupported notification priority')

    user = db.session.get(User, user_id)
    if (
        not user
        or not user.is_active
        or user.deleted_at is not None
        or str(user.tenant_id) != str(tenant_id)
    ):
        return None

    notification = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        body=body,
        notification_type=notification_type,
        priority=priority,
        action_url=action_url,
        metadata_json=metadata or {},
    )
    db.session.add(notification)
    if commit:
        db.session.commit()
    return notification


def notify_users(user_ids: Iterable, **kwargs):
    created = []
    for user_id in dict.fromkeys(user_ids or []):
        notification = create_notification(user_id=user_id, **kwargs)
        if notification:
            created.append(notification)
    return created


def mark_notification_read(notification):
    if notification.read_at is None:
        notification.read_at = utcnow()
    return notification
