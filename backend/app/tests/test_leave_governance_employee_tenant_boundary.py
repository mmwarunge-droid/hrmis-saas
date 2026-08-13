from datetime import date

import pytest

from app.extensions import db
from app.models import Employee, Tenant, User
from app.services.auth_service import register_user
from app.services.leave_policy_service import configure_leave_governance


def _create_candidate(
    tenant_id,
    *,
    email,
    employee_number,
    employee_tenant_id=None,
):
    user = register_user({
        'tenant_id': tenant_id,
        'email': email,
        'first_name': 'Governance',
        'last_name': employee_number,
        'password': 'StrongPass123!',
        'roles': ['EMPLOYEE'],
    })
    employee = Employee(
        tenant_id=employee_tenant_id or tenant_id,
        user_id=user.id,
        employee_number=employee_number,
        first_name='Governance',
        last_name=employee_number,
        email=f'{employee_number.lower()}@profile.test',
        hire_date=date(2025, 1, 1),
    )
    db.session.add(employee)
    db.session.flush()
    return user


def test_leave_governance_rejects_owner_with_cross_tenant_employee_profile(
    app,
    tenant,
    admin_user,
):
    with app.app_context():
        actor_id = db.session.merge(admin_user).id
        foreign_tenant = Tenant(
            name='Foreign Governance Owner Tenant',
            slug='foreign-governance-owner',
        )
        db.session.add(foreign_tenant)
        db.session.flush()

        owner = _create_candidate(
            tenant.id,
            email='governance.owner.boundary@acme.test',
            employee_number='GOV-OWNER-BOUNDARY',
            employee_tenant_id=foreign_tenant.id,
        )
        alternate = _create_candidate(
            tenant.id,
            email='governance.alternate.valid@acme.test',
            employee_number='GOV-ALT-VALID',
        )
        owner_id = owner.id
        alternate_id = alternate.id
        db.session.commit()

        actor = db.session.get(User, actor_id)
        with pytest.raises(
            ValueError,
            match='organization_owner_user_id',
        ):
            configure_leave_governance(
                tenant.id,
                actor,
                owner_id,
                alternate_id,
            )

        configured_tenant = db.session.get(Tenant, tenant.id)
        assert configured_tenant.organization_owner_user_id is None
        assert configured_tenant.leave_alternate_approver_user_id is None


def test_leave_governance_rejects_alternate_with_cross_tenant_employee_profile(
    app,
    tenant,
    admin_user,
):
    with app.app_context():
        actor_id = db.session.merge(admin_user).id
        foreign_tenant = Tenant(
            name='Foreign Governance Alternate Tenant',
            slug='foreign-governance-alternate',
        )
        db.session.add(foreign_tenant)
        db.session.flush()

        owner = _create_candidate(
            tenant.id,
            email='governance.owner.valid@acme.test',
            employee_number='GOV-OWNER-VALID',
        )
        alternate = _create_candidate(
            tenant.id,
            email='governance.alternate.boundary@acme.test',
            employee_number='GOV-ALT-BOUNDARY',
            employee_tenant_id=foreign_tenant.id,
        )
        owner_id = owner.id
        alternate_id = alternate.id
        db.session.commit()

        actor = db.session.get(User, actor_id)
        with pytest.raises(
            ValueError,
            match='alternate_approver_user_id',
        ):
            configure_leave_governance(
                tenant.id,
                actor,
                owner_id,
                alternate_id,
            )

        configured_tenant = db.session.get(Tenant, tenant.id)
        assert configured_tenant.organization_owner_user_id is None
        assert configured_tenant.leave_alternate_approver_user_id is None


def test_leave_governance_retains_same_tenant_employee_candidates(
    app,
    tenant,
    admin_user,
):
    with app.app_context():
        actor_id = db.session.merge(admin_user).id
        owner = _create_candidate(
            tenant.id,
            email='governance.owner.same-tenant@acme.test',
            employee_number='GOV-OWNER-SAME',
        )
        alternate = _create_candidate(
            tenant.id,
            email='governance.alternate.same-tenant@acme.test',
            employee_number='GOV-ALT-SAME',
        )
        owner_id = owner.id
        alternate_id = alternate.id
        db.session.commit()

        actor = db.session.get(User, actor_id)
        configured_tenant = configure_leave_governance(
            tenant.id,
            actor,
            owner_id,
            alternate_id,
        )

        assert configured_tenant.organization_owner_user_id == owner_id
        assert configured_tenant.leave_alternate_approver_user_id == alternate_id
