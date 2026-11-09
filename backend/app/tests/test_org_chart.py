from datetime import date
from types import SimpleNamespace

from app.extensions import db
from app.models import Department, Employee, Tenant
from app.services.org_chart_service import build_org_chart


def person(key, manager=None, tenant="one"):
    return SimpleNamespace(
        id=key,
        manager_id=manager,
        tenant_id=tenant,
        department=None,
        full_name=key,
        employee_number=key,
        profile_photo_url=None,
        job_title="Engineer",
        work_location="Nairobi",
        employment_status="active",
        email=f"{key}@example.test",
        hire_date=date(2020, 1, 1),
    )


def test_counts_multiple_roots_orphans_and_cycles():
    result = build_org_chart(
        [
            person("a"),
            person("b", "a"),
            person("c", "b"),
            person("d"),
            person("e", "missing"),
            person("f", "g"),
            person("g", "f"),
            person("h", "h"),
        ]
    )
    rows = {n["id"]: n for n in result["items"]}
    assert rows["a"]["direct_report_count"] == 1
    assert rows["a"]["indirect_report_count"] == 1
    assert rows["b"]["indirect_report_count"] == 0
    assert len(rows) == 8
    assert {i["code"] for i in result["integrity_issues"]} == {
        "manager_not_visible",
        "self_reporting",
        "reporting_cycle",
    }
    seen, stack = set(), list(result["roots"])
    while stack:
        node = stack.pop()
        assert node["id"] not in seen
        seen.add(node["id"])
        stack.extend(node["children"])
    assert len(seen) == 8


def test_deep_hierarchy_without_recursive_processing():
    result = build_org_chart([person(str(i), str(i - 1) if i else None) for i in range(5000)])
    assert result["meta"]["max_depth"] == 5000
    assert result["items"][0]["indirect_report_count"] == 4998


def test_flat_api_is_tenant_scoped_and_excludes_private_fields(client, auth_headers, app, tenant):
    with app.app_context():
        other = Tenant(name="Other", slug="other-org")
        db.session.add(other)
        db.session.flush()
        department = Department(name="Secret department", tenant_id=other.id)
        outsider = Employee(
            tenant_id=other.id,
            employee_number="OTHER",
            first_name="Secret",
            last_name="Person",
            email="secret@example.test",
            hire_date=date(2020, 1, 1),
        )
        db.session.add_all([department, outsider])
        db.session.flush()
        employee = Employee(
            tenant_id=tenant.id,
            employee_number="OWN",
            first_name="Visible",
            last_name="Person",
            email="visible@example.test",
            hire_date=date(2020, 1, 1),
            manager_id=outsider.id,
            department_id=department.id,
            address="Private home",
            phone="Private phone",
            national_identifier_last4="1234",
        )
        inactive = Employee(
            tenant_id=tenant.id,
            employee_number="OLD",
            first_name="Former",
            last_name="Person",
            email="former@example.test",
            hire_date=date(2020, 1, 1),
            employment_status="terminated",
        )
        db.session.add_all([employee, inactive])
        db.session.commit()
        other_id = str(other.id)
    response = client.get(f"/api/employees/org-chart?format=flat&tenant_id={other_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert "roots" not in data
    assert len(data["items"]) == 1
    row = data["items"][0]
    assert row["full_name"] == "Visible Person"
    assert row["manager_id"] is None and row["department_name"] is None
    assert not {"phone", "address", "national_identifier_last4", "date_of_birth"} & row.keys()
    assert "Secret" not in response.get_data(as_text=True)
    assert data["integrity_issues"][0]["code"] == "manager_not_visible"


def test_org_chart_requires_authentication(client):
    assert client.get("/api/employees/org-chart?format=flat").status_code == 401


def test_authenticated_user_without_employee_permission_cannot_read_chart(client, auth_headers, admin_user, app):
    from app.models import User, UserRole

    with app.app_context():
        user = User.query.filter_by(email="admin@acme.test").one()
        UserRole.query.filter_by(user_id=user.id).delete()
        db.session.commit()
    response = client.get("/api/employees/org-chart?format=flat", headers=auth_headers)
    assert response.status_code == 403


def test_manager_must_be_same_tenant_and_eligible(client, auth_headers, app, tenant):
    from app.tests.test_employees import _create_employee

    employee = _create_employee(client, auth_headers)
    with app.app_context():
        other = Tenant(name="Other manager", slug="other-manager")
        db.session.add(other)
        db.session.flush()
        foreign = Employee(
            tenant_id=other.id,
            employee_number="F",
            first_name="F",
            last_name="M",
            email="f@example.test",
            hire_date=date(2020, 1, 1),
        )
        inactive = Employee(
            tenant_id=tenant.id,
            employee_number="I",
            first_name="I",
            last_name="M",
            email="i@example.test",
            hire_date=date(2020, 1, 1),
            employment_status="terminated",
        )
        db.session.add_all([foreign, inactive])
        db.session.commit()
        ids = [str(foreign.id), str(inactive.id)]
    for manager_id in ids:
        response = client.patch(
            f"/api/employees/{employee['id']}", headers=auth_headers, json={"manager_id": manager_id}
        )
        assert response.status_code == 400


def test_manager_update_refreshes_chart_counts_and_keeps_job_history(client, auth_headers):
    from app.tests.test_employees import _create_employee

    leader = _create_employee(client, auth_headers, employee_number="LEAD", email="lead@test.example")
    report = _create_employee(client, auth_headers, employee_number="REPORT", email="report@test.example")
    changed = client.patch(f"/api/employees/{report['id']}", headers=auth_headers, json={"manager_id": leader["id"]})
    assert changed.status_code == 200
    data = client.get("/api/employees/org-chart?format=flat", headers=auth_headers).get_json()["data"]
    rows = {row["id"]: row for row in data["items"]}
    assert rows[leader["id"]]["direct_report_count"] == 1
    assert rows[report["id"]]["manager_id"] == leader["id"]
    history = client.get(f"/api/employees/{report['id']}/job-history", headers=auth_headers)
    assert history.status_code == 200
    assert leader["id"] in history.get_data(as_text=True)
