import os
import threading
from uuid import uuid4

import pytest

from app import create_app
from app.config import DevelopmentConfig
from app.extensions import db
from app.models import AccountToken, Tenant, User
from app.services import account_recovery_service
from app.services.account_recovery_service import issue_account_token
from app.services.auth_service import register_user


@pytest.fixture()
def postgres_token_app():
    database_url = os.getenv('HRMIS_PG_TEST_URL')
    if not database_url:
        pytest.skip('HRMIS_PG_TEST_URL is required for PostgreSQL concurrency tests')

    original_database_url = DevelopmentConfig.SQLALCHEMY_DATABASE_URI
    DevelopmentConfig.SQLALCHEMY_DATABASE_URI = database_url

    app = create_app('development')
    app.config['TESTING'] = True

    tenant_id = None
    user_id = None

    try:
        with app.app_context():
            marker = uuid4().hex

            tenant = Tenant(
                name=f'Concurrency Test {marker}',
                slug=f'concurrency-{marker}',
                country='Kenya',
            )
            db.session.add(tenant)
            db.session.flush()

            user = register_user(
                {
                    'tenant_id': tenant.id,
                    'email': f'concurrency-{marker}@example.test',
                    'first_name': 'Concurrency',
                    'last_name': 'Token',
                    'password': 'StrongConcurrencyPass123!',
                    'roles': ['EMPLOYEE'],
                },
                commit=False,
            )
            db.session.commit()

            tenant_id = tenant.id
            user_id = user.id

        yield app, user_id

    finally:
        if user_id is not None:
            with app.app_context():
                user = db.session.get(User, user_id)
                if user is not None:
                    db.session.delete(user)

                tenant = db.session.get(Tenant, tenant_id)
                if tenant is not None:
                    db.session.delete(tenant)

                db.session.commit()

        DevelopmentConfig.SQLALCHEMY_DATABASE_URI = original_database_url


def test_concurrent_token_issuance_leaves_only_one_active_token(
    postgres_token_app,
    monkeypatch,
):
    app, user_id = postgres_token_app

    # Both transactions must complete the "consume existing tokens" UPDATE
    # before either inserts its replacement token. issue_account_token()
    # calls token_urlsafe immediately after that UPDATE, so this barrier makes
    # the race deterministic instead of relying on thread timing.
    issuance_barrier = threading.Barrier(2)
    worker_errors = []

    def synchronized_token_urlsafe(_size):
        issuance_barrier.wait(timeout=10)
        return f'concurrent-token-{threading.current_thread().name}-{uuid4().hex}'

    monkeypatch.setattr(
        account_recovery_service.secrets,
        'token_urlsafe',
        synchronized_token_urlsafe,
    )

    def issue_token():
        try:
            with app.app_context():
                user = db.session.get(User, user_id)
                issue_account_token(
                    user,
                    AccountToken.PURPOSE_PASSWORD_RESET,
                )
                db.session.commit()
        except Exception as exc:
            worker_errors.append(exc)
        finally:
            with app.app_context():
                db.session.remove()

    workers = [
        threading.Thread(target=issue_token, name='issuer-a'),
        threading.Thread(target=issue_token, name='issuer-b'),
    ]

    for worker in workers:
        worker.start()

    for worker in workers:
        worker.join(timeout=15)

    assert not any(worker.is_alive() for worker in workers)
    assert worker_errors == []

    with app.app_context():
        active_tokens = AccountToken.query.filter(
            AccountToken.user_id == user_id,
            AccountToken.purpose == AccountToken.PURPOSE_PASSWORD_RESET,
            AccountToken.consumed_at.is_(None),
        ).all()

        assert len(active_tokens) == 1
