from types import SimpleNamespace

import pytest

from app import create_app
from app.extensions import db
from app.models import Tenant
from app.services.auth_service import register_user
from app.services.rbac_service import seed_roles_permissions


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        seed_roles_permissions()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def tenant(app):
    with app.app_context():
        t = Tenant(name='Acme Ltd', slug='acme', country='Kenya')
        db.session.add(t)
        db.session.commit()
        return SimpleNamespace(id=t.id)


@pytest.fixture()
def admin_user(app, tenant):
    with app.app_context():
        return register_user({
            'tenant_id': tenant.id,
            'email': 'admin@acme.test',
            'first_name': 'Admin',
            'last_name': 'User',
            'password': 'StrongPass123!',
            'roles': ['CLIENT_ADMIN'],
        })


@pytest.fixture()
def auth_headers(client, admin_user):
    res = client.post('/api/auth/login', json={'email': 'admin@acme.test', 'password': 'StrongPass123!'})
    token = res.get_json()['data']['access_token']
    return {'Authorization': f'Bearer {token}'}
