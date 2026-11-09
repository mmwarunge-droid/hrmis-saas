"""Concurrent reporting edits, ONLY against a disposable local PostgreSQL schema."""

import os
import threading
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Employee, Tenant
from app.services.employee_service import _assert_valid_manager


def test_concurrent_inverse_manager_changes_cannot_create_cycle():
    url = os.getenv("HRMIS_ORG_TEST_URL")
    if not url:
        pytest.skip("HRMIS_ORG_TEST_URL requires a disposable local PostgreSQL database")
    assert "127.0.0.1" in url and "hrmis_org_test" in url
    schema = "org_" + uuid4().hex
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    original = TestingConfig.SQLALCHEMY_DATABASE_URI
    original_options = getattr(TestingConfig, "SQLALCHEMY_ENGINE_OPTIONS", {})
    TestingConfig.SQLALCHEMY_DATABASE_URI = url
    TestingConfig.SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"options": f"-csearch_path={schema}"}}
    app = create_app("testing")
    results = []
    barrier = threading.Barrier(2)
    try:
        with app.app_context():
            db.create_all()
            tenant = Tenant(name="Concurrency", slug="concurrency")
            db.session.add(tenant)
            db.session.flush()
            people = [
                Employee(
                    tenant_id=tenant.id,
                    employee_number=str(i),
                    first_name=str(i),
                    last_name="Test",
                    email=f"{i}@test.example",
                    hire_date=date(2020, 1, 1),
                )
                for i in range(2)
            ]
            db.session.add_all(people)
            db.session.commit()
            ids, tenant_id = [p.id for p in people], tenant.id

        def change(index):
            with app.app_context():
                try:
                    employee = db.session.get(Employee, ids[index])
                    # Load both identities before the competing commit to test refresh semantics.
                    db.session.get(Employee, ids[1 - index])
                    barrier.wait(timeout=10)
                    _assert_valid_manager(employee, ids[1 - index], tenant_id)
                    employee.manager_id = ids[1 - index]
                    db.session.commit()
                    results.append("saved")
                except ValueError:
                    db.session.rollback()
                    results.append("rejected")
                except Exception as error:
                    results.append(type(error).__name__)
                    db.session.rollback()

        threads = [threading.Thread(target=change, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
            assert not thread.is_alive()
        assert sorted(results) == ["rejected", "saved"]
    finally:
        TestingConfig.SQLALCHEMY_DATABASE_URI = original
        TestingConfig.SQLALCHEMY_ENGINE_OPTIONS = original_options
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        with engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        engine.dispose()
