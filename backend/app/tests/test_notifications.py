from app.extensions import db
from app.models import Notification, User
from app.services.auth_service import register_user
from sqlalchemy import inspect


def test_notification_feed_read_state_is_user_scoped(
    app,
    client,
    tenant,
    admin_user,
    auth_headers,
):
    admin_id = inspect(admin_user).identity[0]
    with app.app_context():
        other = register_user({
            'tenant_id': tenant.id,
            'email': 'other@acme.test',
            'first_name': 'Other',
            'last_name': 'User',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        admin = db.session.get(User, admin_id)
        first = Notification(
            tenant_id=tenant.id,
            user_id=admin.id,
            title='Approval needed',
            body='Review the request.',
            notification_type='leave_approval',
            priority='high',
            action_url='/leave',
        )
        second = Notification(
            tenant_id=tenant.id,
            user_id=admin.id,
            title='Onboarding assigned',
            notification_type='onboarding',
        )
        hidden = Notification(
            tenant_id=tenant.id,
            user_id=other.id,
            title='Private notification',
            notification_type='system',
        )
        db.session.add_all([first, second, hidden])
        db.session.commit()
        first_id = str(first.id)
        hidden_id = str(hidden.id)

    response = client.get('/api/notifications', headers=auth_headers)
    assert response.status_code == 200
    payload = response.get_json()['data']
    assert payload['unread_count'] == 2
    assert {item['title'] for item in payload['items']} == {
        'Approval needed',
        'Onboarding assigned',
    }
    assert payload['items'][0]['created_at']

    read = client.patch(
        f'/api/notifications/{first_id}/read',
        headers=auth_headers,
    )
    assert read.status_code == 200
    assert read.get_json()['data']['read_at']

    forbidden = client.patch(
        f'/api/notifications/{hidden_id}/read',
        headers=auth_headers,
    )
    assert forbidden.status_code == 404

    read_all = client.post(
        '/api/notifications/read-all',
        headers=auth_headers,
    )
    assert read_all.status_code == 200
    assert read_all.get_json()['data']['updated'] == 1

    after = client.get('/api/notifications?unread=true', headers=auth_headers)
    assert after.status_code == 200
    assert after.get_json()['data']['unread_count'] == 0
    assert after.get_json()['data']['items'] == []
