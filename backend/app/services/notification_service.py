from collections.abc import Iterable
from html import escape
from urllib.parse import urlparse

from flask import current_app

from app.extensions import db
from app.models import Notification, User
from app.models.base import utcnow
from app.utils.email import EmailDeliveryError, send_email

VALID_PRIORITIES = {'low', 'normal', 'high', 'urgent'}


def _safe_action_url(action_url):
    if not action_url:
        return None
    parsed = urlparse(action_url)
    if parsed.scheme or parsed.netloc or not action_url.startswith('/') or action_url.startswith('//'):
        raise ValueError('Notification action_url must be an internal application path')
    return action_url


def _absolute_action_url(action_url):
    if not action_url:
        return None
    return f"{current_app.config['FRONTEND_URL'].rstrip('/')}{action_url}"


def _deliver_notification_email(user, title, body, action_url):
    absolute_url = _absolute_action_url(action_url)
    text = body or title
    if absolute_url:
        text = f"{text}\n\nOpen this task in Kinetic:\n{absolute_url}"
    html = None
    if absolute_url:
        html = (
            f'<p>{escape(body or title)}</p>'
            f'<p><a href="{escape(absolute_url, quote=True)}">View task in Kinetic</a></p>'
        )
    try:
        return send_email(
            user.email,
            title,
            text,
            html_body=html,
            reply_to=current_app.config.get('MAIL_REPLY_TO'),
        )
    except EmailDeliveryError:
        current_app.logger.exception(
            'notification.email_delivery_failed user_id=%s',
            user.id,
        )
        return {'queued': False, 'transport': current_app.config.get('MAIL_TRANSPORT')}


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
    email_delivery=None,
    commit=False,
):
    if not tenant_id or not user_id:
        return None
    if priority not in VALID_PRIORITIES:
        raise ValueError('Unsupported notification priority')

    action_url = _safe_action_url(action_url)
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

    should_email = bool(action_url) if email_delivery is None else bool(email_delivery)
    if should_email:
        delivery = _deliver_notification_email(user, title, body, action_url)
        notification.metadata_json = {
            **(notification.metadata_json or {}),
            'email_delivery': delivery,
        }

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
