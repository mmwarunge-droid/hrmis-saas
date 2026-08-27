from datetime import date

import pytest
from sqlalchemy import inspect

from app.extensions import db
from app.models import Employee, LeaveBalance, LeaveRequest, LeaveType, Tenant, User
from app.services.auth_service import register_user
from app.services.leave_policy_service import (
    apply_standard_policy_pack,
    configure_leave_governance,
    leave_setup_status,
)
from app.services.leave_service import (
    create_leave_request,
    decide_leave_request,
    resolve_required_approver,
)


def _identity(model):
    return inspect(model).identity[0]


def _create_user_employee(
    tenant_id,
    *,
    email,
    employee_number,
    first_name,
    roles=None,
    manager_id=None,
):
    user = register_user(
        {
            'tenant_id': tenant_id,
            'email': email,
            'first_name': first_name,
            'last_name': 'User',
            'password': 'StrongLeavePass123!',
            'roles': roles or ['EMPLOYEE'],
        },
        commit=False,
    )
    employee = Employee(
        tenant_id=tenant_id,
        user_id=user.id,
        employee_number=employee_number,
        first_name=first_name,
        last_name='User',
        email=email,
        hire_date=date(2026, 1, 1),
        employment_status='active',
        employment_type='full_time',
        manager_id=manager_id,
    )
    db.session.add(employee)
    db.session.commit()
    return user.id, employee.id


def _configure_governance_and_pack(
    tenant_id,
    actor,
    *,
    owner_id,
    alternate_id,
):
    configure_leave_governance(
        tenant_id,
        actor,
        owner_id,
        alternate_id,
    )
    apply_standard_policy_pack(
        tenant_id,
        actor,
        as_of_date=date(2026, 7, 31),
    )


def test_standard_pack_configures_governance_and_balances(
    app,
    tenant,
    admin_user,
):
    tenant_id = tenant.id
    admin_id = _identity(admin_user)

    with app.app_context():
        owner_id, _ = _create_user_employee(
            tenant_id,
            email='owner@acme.test',
            employee_number='OWN-001',
            first_name='Owner',
            roles=['MANAGER'],
        )
        alternate_id, _ = _create_user_employee(
            tenant_id,
            email='alternate@acme.test',
            employee_number='ALT-001',
            first_name='Alternate',
            roles=['MANAGER'],
        )
        actor = db.session.get(User, admin_id)

        _configure_governance_and_pack(
            tenant_id,
            actor,
            owner_id=owner_id,
            alternate_id=alternate_id,
        )

        saved_tenant = db.session.get(Tenant, tenant_id)
        assert saved_tenant.organization_owner_user_id == owner_id
        assert (
            saved_tenant.leave_alternate_approver_user_id
            == alternate_id
        )

        owner = db.session.get(User, owner_id)
        assert 'ORGANIZATION_OWNER' in owner.role_names

        annual = LeaveType.query.filter_by(
            tenant_id=tenant_id,
            code='annual_leave',
        ).one()
        assert annual.accrual_method == 'monthly'
        assert annual.entitlement_mode == 'accrued'

        balance_count = LeaveBalance.query.filter_by(
            tenant_id=tenant_id,
            year=2026,
        ).count()
        assert balance_count > 0

        status = leave_setup_status(tenant_id, actor)
        assert status['active_policy_count'] == 12
        assert status['organization_owner']['id'] == str(owner_id)


def test_employee_request_routes_to_manager_and_blocks_self_approval(
    app,
    tenant,
    admin_user,
):
    tenant_id = tenant.id
    admin_id = _identity(admin_user)

    with app.app_context():
        owner_id, _ = _create_user_employee(
            tenant_id,
            email='owner2@acme.test',
            employee_number='OWN-002',
            first_name='Owner',
            roles=['MANAGER'],
        )
        alternate_id, _ = _create_user_employee(
            tenant_id,
            email='alternate2@acme.test',
            employee_number='ALT-002',
            first_name='Alternate',
            roles=['MANAGER'],
        )
        manager_user_id, manager_employee_id = _create_user_employee(
            tenant_id,
            email='manager@acme.test',
            employee_number='MGR-001',
            first_name='Manager',
            roles=['MANAGER'],
        )
        employee_user_id, employee_id = _create_user_employee(
            tenant_id,
            email='employee@acme.test',
            employee_number='EMP-001',
            first_name='Employee',
            manager_id=manager_employee_id,
        )

        actor = db.session.get(User, admin_id)
        _configure_governance_and_pack(
            tenant_id,
            actor,
            owner_id=owner_id,
            alternate_id=alternate_id,
        )

        annual = LeaveType.query.filter_by(
            tenant_id=tenant_id,
            code='annual_leave',
        ).one()
        employee_user = db.session.get(User, employee_user_id)
        request_obj = create_leave_request(
            {
                'employee_id': employee_id,
                'leave_type_id': annual.id,
                'start_date': date(2026, 8, 3),
                'end_date': date(2026, 8, 7),
                'reason': 'Rest',
            },
            tenant_id,
            employee_user,
        )

        assert request_obj.status == 'pending'
        assert request_obj.required_approver_id == manager_user_id
        assert request_obj.approval_route == 'employee_to_manager'

        with pytest.raises(ValueError, match='own leave'):
            decide_leave_request(
                request_obj,
                'approved',
                employee_user,
            )

        manager_user = db.session.get(User, manager_user_id)
        decided = decide_leave_request(
            request_obj,
            'approved',
            manager_user,
            'Approved',
        )
        assert decided.status == 'approved'

        balance = LeaveBalance.query.filter_by(
            tenant_id=tenant_id,
            employee_id=employee_id,
            leave_type_id=annual.id,
            year=2026,
        ).one()
        assert float(balance.used_days) == 5.0


def test_client_admin_request_routes_to_organization_owner(
    app,
    tenant,
    admin_user,
):
    tenant_id = tenant.id
    admin_id = _identity(admin_user)

    with app.app_context():
        owner_id, _ = _create_user_employee(
            tenant_id,
            email='owner3@acme.test',
            employee_number='OWN-003',
            first_name='Owner',
            roles=['MANAGER'],
        )
        alternate_id, _ = _create_user_employee(
            tenant_id,
            email='alternate3@acme.test',
            employee_number='ALT-003',
            first_name='Alternate',
            roles=['MANAGER'],
        )

        actor = db.session.get(User, admin_id)
        admin_employee = Employee(
            tenant_id=tenant_id,
            user_id=actor.id,
            employee_number='HR-001',
            first_name=actor.first_name,
            last_name=actor.last_name,
            email=actor.email,
            hire_date=date(2026, 1, 1),
            employment_status='active',
            employment_type='full_time',
        )
        db.session.add(admin_employee)
        db.session.commit()

        _configure_governance_and_pack(
            tenant_id,
            actor,
            owner_id=owner_id,
            alternate_id=alternate_id,
        )

        annual = LeaveType.query.filter_by(
            tenant_id=tenant_id,
            code='annual_leave',
        ).one()
        request_obj = create_leave_request(
            {
                'employee_id': admin_employee.id,
                'leave_type_id': annual.id,
                'start_date': date(2026, 9, 7),
                'end_date': date(2026, 9, 9),
                'reason': 'Personal leave',
            },
            tenant_id,
            actor,
        )

        assert request_obj.required_approver_id == owner_id
        assert request_obj.approval_route == 'hr_to_owner'

        owner = db.session.get(User, owner_id)
        decided = decide_leave_request(
            request_obj,
            'approved',
            owner,
        )
        assert decided.status == 'approved'


def test_leave_request_rejects_overlapping_dates(
    app,
    tenant,
    admin_user,
):
    tenant_id = tenant.id
    admin_id = _identity(admin_user)

    with app.app_context():
        owner_id, _ = _create_user_employee(
            tenant_id,
            email='owner4@acme.test',
            employee_number='OWN-004',
            first_name='Owner',
            roles=['MANAGER'],
        )
        alternate_id, _ = _create_user_employee(
            tenant_id,
            email='alternate4@acme.test',
            employee_number='ALT-004',
            first_name='Alternate',
            roles=['MANAGER'],
        )
        employee_user_id, employee_id = _create_user_employee(
            tenant_id,
            email='employee2@acme.test',
            employee_number='EMP-002',
            first_name='Employee',
        )

        actor = db.session.get(User, admin_id)
        _configure_governance_and_pack(
            tenant_id,
            actor,
            owner_id=owner_id,
            alternate_id=alternate_id,
        )

        annual = LeaveType.query.filter_by(
            tenant_id=tenant_id,
            code='annual_leave',
        ).one()
        employee_user = db.session.get(User, employee_user_id)

        create_leave_request(
            {
                'employee_id': employee_id,
                'leave_type_id': annual.id,
                'start_date': date(2026, 10, 5),
                'end_date': date(2026, 10, 7),
            },
            tenant_id,
            employee_user,
        )

        with pytest.raises(ValueError, match='overlapping'):
            create_leave_request(
                {
                    'employee_id': employee_id,
                    'leave_type_id': annual.id,
                    'start_date': date(2026, 10, 7),
                    'end_date': date(2026, 10, 9),
                },
                tenant_id,
                employee_user,
            )

        assert LeaveRequest.query.filter_by(
            tenant_id=tenant_id,
            employee_id=employee_id,
        ).count() == 1


def test_leave_routing_ignores_cross_tenant_employee_user_link(
    app,
    tenant,
):
    """Malformed Employee.user_id must not import another tenant's roles."""
    with app.app_context():
        tenant_id = tenant.id

        owner = register_user({
            'tenant_id': tenant_id,
            'email': 'leave.boundary.owner@acme.test',
            'first_name': 'Boundary',
            'last_name': 'Owner',
            'password': 'StrongPass123!',
            'roles': ['MANAGER'],
        })
        alternate = register_user({
            'tenant_id': tenant_id,
            'email': 'leave.boundary.alternate@acme.test',
            'first_name': 'Boundary',
            'last_name': 'Alternate',
            'password': 'StrongPass123!',
            'roles': ['MANAGER'],
        })
        requester = register_user({
            'tenant_id': tenant_id,
            'email': 'leave.boundary.requester@acme.test',
            'first_name': 'Boundary',
            'last_name': 'Requester',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })

        foreign_tenant = Tenant(
            name='Leave Routing Foreign Tenant',
            slug='leave-routing-foreign-tenant',
            country='Kenya',
        )
        db.session.add(foreign_tenant)
        db.session.flush()

        foreign_owner = register_user({
            'tenant_id': foreign_tenant.id,
            'email': 'leave.boundary.foreign-owner@other.test',
            'first_name': 'Foreign',
            'last_name': 'Owner',
            'password': 'StrongPass123!',
            'roles': ['ORGANIZATION_OWNER'],
        })

        employee = Employee(
            tenant_id=tenant_id,
            user_id=foreign_owner.id,
            employee_number='LEAVE-XTENANT-USER',
            first_name='Malformed',
            last_name='Link',
            email='leave.boundary.employee@acme.test',
            hire_date=date(2026, 1, 1),
            employment_status='active',
            employment_type='full_time',
        )
        db.session.add(employee)

        current_tenant = db.session.get(Tenant, tenant_id)
        current_tenant.organization_owner_user_id = owner.id
        current_tenant.leave_alternate_approver_user_id = alternate.id
        db.session.commit()

        employee = db.session.get(Employee, employee.id)
        requester = db.session.get(User, requester.id)
        current_tenant = db.session.get(Tenant, tenant_id)

        approver, route = resolve_required_approver(
            employee,
            current_tenant,
            requester,
        )

        assert approver.id == owner.id
        assert route == 'employee_to_owner'
