import os

from app import create_app
from app.extensions import db
from app.models import Tenant, User
from app.services.auth_service import register_user
from app.services.rbac_service import seed_roles_permissions


environment = (os.getenv('APP_ENV') or os.getenv('FLASK_ENV') or 'development').lower()
if environment == 'production':
    raise RuntimeError('Demo seeding is disabled in production. Use: flask --app run.py bootstrap-admin')

app = create_app(environment)

with app.app_context():
    seed_roles_permissions(commit=False)
    tenant = Tenant.query.filter_by(slug='demo').first()
    if not tenant:
        tenant = Tenant(name='Demo Company', slug='demo', country='Kenya', industry='Professional Services')
        db.session.add(tenant)
        db.session.flush()
    if not User.query.filter_by(email='admin@example.com').first():
        register_user({
            'tenant_id': tenant.id,
            'email': 'admin@example.com',
            'first_name': 'Demo',
            'last_name': 'Admin',
            'password': os.getenv('SEED_ADMIN_PASSWORD', 'ChangeMe123!'),
            'roles': ['CLIENT_ADMIN'],
        })
    else:
        db.session.commit()
    print('Development demo seed completed')
