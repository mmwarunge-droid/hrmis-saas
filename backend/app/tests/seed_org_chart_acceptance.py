"""Seed a fresh, migrated disposable local database for org-chart browser acceptance."""

import sys
import os
import json
from pathlib import Path
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from datetime import date
from app import create_app
from app.extensions import db
from app.models import Tenant, Employee, Department
from app.models.base import utcnow
from app.services.auth_service import register_user
from app.services.mfa_service import _encrypt_secret
from app.services.rbac_service import seed_roles_permissions

url = make_url(os.environ["DATABASE_URL"])
if url.host not in {"localhost", "127.0.0.1"} or url.database != "hrmis_org_test":
    raise SystemExit("Only the disposable local hrmis_org_test database is allowed")
if os.environ.get("HRMIS_ORG_ACCEPTANCE") != "1":
    raise SystemExit("Set HRMIS_ORG_ACCEPTANCE=1 for explicit synthetic seeding")
for key in ("ORG_TEST_PASSWORD", "DEMO_MFA_SECRET", "ORG_TEST_FIXTURE"):
    if not os.environ.get(key):
        raise SystemExit(f"{key} is required; use disposable values only")
if os.environ.get("MAIL_TRANSPORT") != "memory":
    raise SystemExit("MAIL_TRANSPORT=memory is required for isolated acceptance")
app = create_app("development")
with app.app_context():
    if Tenant.query.first() is not None:
        raise SystemExit("Refusing to seed a nonempty tenant database")
    seed_roles_permissions()
    tenants = [
        Tenant(name="Org Chart Acceptance A", slug="org-chart-acceptance-a"),
        Tenant(name="Org Chart Acceptance B", slug="org-chart-acceptance-b"),
    ]
    db.session.add_all(tenants)
    db.session.commit()
    users = []
    for i, t in enumerate(tenants):
        u = register_user(
            {
                "tenant_id": t.id,
                "email": f"admin-{i}@org-chart.test",
                "first_name": "Acceptance",
                "last_name": f"Admin{i}",
                "password": os.environ["ORG_TEST_PASSWORD"],
                "roles": ["CLIENT_ADMIN"],
            }
        )
        u.mfa_secret_encrypted = _encrypt_secret(os.environ["DEMO_MFA_SECRET"])
        u.mfa_enabled_at = utcnow()
        u.email_verified_at = utcnow()
        users.append(u)
    reader = register_user(
        {
            "tenant_id": tenants[0].id,
            "email": "reader@org-chart.test",
            "first_name": "Read",
            "last_name": "Only",
            "password": os.environ["ORG_TEST_PASSWORD"],
            "roles": ["EMPLOYEE"],
        }
    )
    departments = [Department(tenant_id=tenants[0].id, name=n) for n in ["Engineering", "People"]]
    db.session.add_all(departments)
    db.session.flush()
    people = []
    for i in range(1000):
        e = Employee(
            tenant_id=tenants[0].id,
            employee_number=f"ORG-{i}",
            first_name=["Amina", "Brian", "Carol"][i] if i < 3 else f"Colleague{i}",
            last_name="Acceptance",
            email=f"employee{i}@org-chart.test",
            hire_date=date(2020, 1, 1),
            job_title="Director" if not i else "Specialist",
            work_location="Nairobi",
            department_id=departments[i % 2].id,
            manager_id=people[(i - 1) // 5].id if i else None,
            user_id=users[0].id if i == 0 else reader.id if i == 3 else None,
        )
        db.session.add(e)
        db.session.flush()
        people.append(e)
    outsider = Employee(
        tenant_id=tenants[1].id,
        employee_number="PRIVATE",
        first_name="OtherTenant",
        last_name="Private",
        email="private@org-chart.test",
        hire_date=date(2020, 1, 1),
        user_id=users[1].id,
    )
    db.session.add(outsider)
    db.session.commit()
    Path(os.environ["ORG_TEST_FIXTURE"]).write_text(
        json.dumps(
            {
                "employees": [str(p.id) for p in people],
                "tenants": [str(t.id) for t in tenants],
                "outsider": str(outsider.id),
            }
        )
    )
    print("1001 synthetic employees, two tenants, two MFA admins and one employee account created.")
