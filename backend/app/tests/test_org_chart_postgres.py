"""Reporting edit concurrency against a disposable local PostgreSQL schema."""

import os
import threading
import time
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Employee, Tenant
from app.services.employee_service import _assert_valid_manager, update_employee


@pytest.fixture()
def reporting_database():
    url = os.getenv("HRMIS_ORG_TEST_URL")
    if not url:
        pytest.skip("HRMIS_ORG_TEST_URL requires a disposable local PostgreSQL database")
    target = make_url(url)
    assert target.host in {"localhost", "127.0.0.1"}
    assert target.database == "hrmis_org_test"
    schema = "org_" + uuid4().hex
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    original = TestingConfig.SQLALCHEMY_DATABASE_URI
    original_options = getattr(TestingConfig, "SQLALCHEMY_ENGINE_OPTIONS", {})
    TestingConfig.SQLALCHEMY_DATABASE_URI = url
    TestingConfig.SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"options": f"-csearch_path={schema}"}}
    app = create_app("testing")
    try:
        with app.app_context():
            db.create_all()
            tenants = [Tenant(name=f"Concurrency {i}", slug=f"concurrency-{i}") for i in range(2)]
            db.session.add_all(tenants)
            db.session.flush()
            people = [
                Employee(
                    tenant_id=tenants[i // 2].id,
                    employee_number=str(i),
                    first_name=str(i),
                    last_name="Test",
                    email=f"{i}@test.example",
                    hire_date=date(2020, 1, 1),
                )
                for i in range(4)
            ]
            db.session.add_all(people)
            db.session.commit()
            ids, tenant_ids = [p.id for p in people], [t.id for t in tenants]
        yield app, ids, tenant_ids
    finally:
        TestingConfig.SQLALCHEMY_DATABASE_URI = original
        TestingConfig.SQLALCHEMY_ENGINE_OPTIONS = original_options
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        with engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        engine.dispose()


def test_concurrent_inverse_manager_changes_cannot_create_cycle(reporting_database):
    app, ids, _ = reporting_database
    results, durations = [], []
    barrier = threading.Barrier(2)

    def change(index):
        with app.app_context():
            start = time.monotonic()
            try:
                employee = db.session.get(Employee, ids[index])
                db.session.get(Employee, ids[1 - index])
                barrier.wait(timeout=10)
                # Exercise history, audit writes and commit, not just validation.
                update_employee(employee, {"manager_id": ids[1 - index]})
                results.append("saved")
            except ValueError:
                db.session.rollback()
                results.append("rejected")
            except Exception as error:
                results.append(type(error).__name__)
                db.session.rollback()
            finally:
                durations.append(time.monotonic() - start)

    threads = [threading.Thread(target=change, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
        assert not thread.is_alive()
    assert sorted(results) == ["rejected", "saved"]
    assert max(durations) < 5
    print(f"Inverse edit transaction max seconds: {max(durations):.4f}")


def test_reporting_lock_allows_foreign_keys_reads_and_other_tenants(reporting_database):
    app, ids, tenant_ids = reporting_database
    held, release = threading.Event(), threading.Event()
    errors = []

    def hold():
        with app.app_context():
            try:
                _assert_valid_manager(db.session.get(Employee, ids[0]), None, tenant_ids[0])
                held.set()
                assert release.wait(timeout=10)
                db.session.rollback()
            except Exception as error:
                errors.append(type(error).__name__)
                held.set()

    thread = threading.Thread(target=hold)
    thread.start()
    assert held.wait(timeout=5)
    try:
        with app.app_context():
            db.session.execute(text("SET LOCAL lock_timeout = '500ms'"))
            # This insert takes a tenant FK KEY SHARE lock. FOR UPDATE would block it.
            employee = Employee(
                tenant_id=tenant_ids[0],
                employee_number="unrelated",
                first_name="Unrelated",
                last_name="Write",
                email="unrelated@test.example",
                hire_date=date(2020, 1, 1),
            )
            db.session.add(employee)
            db.session.commit()
            assert Employee.query.filter_by(tenant_id=tenant_ids[0]).count() == 3
            db.session.execute(text("SET LOCAL lock_timeout = '500ms'"))
            update_employee(db.session.get(Employee, ids[1]), {"manager_id": None, "work_location": "Nairobi"})
            db.session.execute(text("SET LOCAL lock_timeout = '500ms'"))
            update_employee(db.session.get(Employee, ids[2]), {"manager_id": ids[3]})
        with app.app_context():
            db.session.execute(text("SET LOCAL lock_timeout = '200ms'"))
            with pytest.raises(Exception) as error:
                _assert_valid_manager(db.session.get(Employee, ids[1]), ids[0], tenant_ids[0])
            assert getattr(error.value.orig, "pgcode", None) == "55P03"
            db.session.rollback()
    finally:
        release.set()
        thread.join(timeout=10)
    assert not thread.is_alive()
    assert errors == []
