from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required

from app.extensions import db
from app.models import Notification
from app.models.base import utcnow
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import success

notification_bp = Blueprint(
    'notifications',
    __name__,
    url_prefix='/notifications',
)


def _notification_query():
    return Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.tenant_id == current_user.tenant_id,
    )


@notification_bp.get('')
@jwt_required()
def list_notifications():
    page, per_page = get_pagination(default_per_page=12, max_per_page=50)
    query = _notification_query()
    if request.args.get('unread', '').lower() == 'true':
        query = query.filter(Notification.read_at.is_(None))
    notification_type = request.args.get('type', '').strip()
    if notification_type:
        query = query.filter(
            Notification.notification_type == notification_type,
        )
    pagination = query.order_by(
        Notification.read_at.is_not(None),
        Notification.created_at.desc(),
    ).paginate(page=page, per_page=per_page, error_out=False)
    data = paginated_response(pagination)
    data['unread_count'] = _notification_query().filter(
        Notification.read_at.is_(None),
    ).count()
    return success(data)


@notification_bp.patch('/<notification_id>/read')
@jwt_required()
def read_notification(notification_id):
    notification = _notification_query().filter_by(
        id=notification_id,
    ).first_or_404()
    if notification.read_at is None:
        notification.read_at = utcnow()
        db.session.commit()
    return success(notification.to_dict(), 'Notification marked as read')


@notification_bp.post('/read-all')
@jwt_required()
def read_all_notifications():
    updated = _notification_query().filter(
        Notification.read_at.is_(None),
    ).update(
        {Notification.read_at: utcnow()},
        synchronize_session=False,
    )
    db.session.commit()
    return success({'updated': updated}, 'Notifications marked as read')
