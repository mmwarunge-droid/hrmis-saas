from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import inspect

from app.extensions import db
from app.models import (
    Employee,
    LeaveBalance,
    LeaveLedgerEntry,
    LeaveType,
    User,
)
from app.services.auth_service import register_user
from app.services.leave_accrual_service import (
    adjust_leave_balance,
    assert_balance_available,
    balance_scope_query,
    get_or_create_balance,
    initialize_balance_for_policy,
    repair_event_based_balances,
    run_scheduled_accruals,
)
from app.services.leave_service import (
    cancel_leave_request,
    create_leave_request,
    decide_leave_request,
)


def _identity(model):
    return inspect(model).identity[0]


def _user_employee(
    tenant_id,
    *,
    email,
    number,
    first_name,
    roles=None,
    manager_id=None,
):
    user = register_user(
        {
            'tenant_id': tenant_id,
            'email': email,
            'first_name': first_name,
            'last_name': 'Ledger',
            'password': 'StrongLedgerPass123!',
            'roles': roles or ['EMPLOYEE'],
        },
        commit=False,
    )
    employee = Employee(
        tenant_id=tenant_id,
        user_id=user.id,
        employee_number=number,
        first_name=first_name,
        last_name='Ledger',
        email=email,
        hire_date=date(2026, 1, 1),
        employment_status='active',
        employment_type='full_time',
        manager_id=manager_id,
    )
    db.session.add(employee)
    db.session.commit()
    return user, employee


def _policy(tenant_id, *, requires_approval=True, entitlement='5'):
    policy = LeaveType(
        tenant_id=tenant_id,
        code=f'test_{LeaveType.query.count()}',
        name=f'Test leave {LeaveType.query.count()}',
        annual_entitlement_days=Decimal(entitlement),
        accrual_method='annual',
        entitlement_mode='granted_upfront',
        requires_approval=requires_approval,
        carryover_allowed=False,
        max_carryover_days=Decimal('0'),
    )
    db.session.add(policy)
    db.session.commit()
    return policy


def _opening_balance(employee, policy, amount='5', year=2026):
    balance = LeaveBalance(
        tenant_id=employee.tenant_id,
        employee_id=employee.id,
        leave_type_id=policy.id,
        year=year,
        opening_days=Decimal(amount),
        balance_days=Decimal(amount),
    )
    db.session.add(balance)
    db.session.commit()
    return balance


def test_monthly_accrual_is_idempotent(app, tenant):
    with app.app_context():
        employee = Employee(
            tenant_id=tenant.id,
            employee_number='ACC-001',
            first_name='Accrual',
            last_name='Employee',
            email='accrual@example.test',
            hire_date=date(2026, 1, 1),
            employment_status='active',
            employment_type='full_time',
        )
        policy = LeaveType(
            tenant_id=tenant.id,
            code='monthly_annual',
            name='Monthly annual',
            annual_entitlement_days=Decimal('21'),
            accrual_method='monthly',
            entitlement_mode='accrued',
            requires_approval=True,
        )
        db.session.add_all([employee, policy])
        db.session.flush()

        balance, _ = get_or_create_balance(
            tenant.id,
            employee.id,
            policy.id,
            2026,
        )
        initialize_balance_for_policy(
            balance,
            policy,
            employee,
            date(2026, 7, 31),
        )
        db.session.commit()

        assert float(balance.accrued_days) == 12.25
        assert LeaveLedgerEntry.query.filter_by(
            tenant_id=tenant.id,
            event_type='ACCRUAL',
        ).count() == 7

        first = run_scheduled_accruals(
            tenant_id=tenant.id,
            as_of_date=date(2026, 8, 31),
        )
        second = run_scheduled_accruals(
            tenant_id=tenant.id,
            as_of_date=date(2026, 8, 31),
        )

        saved = db.session.get(LeaveBalance, balance.id)
        assert float(saved.accrued_days) == 14.0
        assert first['accrual_entries'] == 1
        assert second['accrual_entries'] == 0
        assert LeaveLedgerEntry.query.filter_by(
            tenant_id=tenant.id,
            event_type='ACCRUAL',
        ).count() == 8


def test_pending_request_reserves_and_rejection_restores_balance(
    app,
    tenant,
):
    with app.app_context():
        manager_user, manager = _user_employee(
            tenant.id,
            email='ledger-manager@example.test',
            number='LED-MGR',
            first_name='Manager',
            roles=['MANAGER'],
        )
        employee_user, employee = _user_employee(
            tenant.id,
            email='ledger-employee@example.test',
            number='LED-EMP',
            first_name='Employee',
            manager_id=manager.id,
        )
        policy = _policy(tenant.id)
        balance = _opening_balance(employee, policy)

        request_obj = create_leave_request(
            {
                'employee_id': employee.id,
                'leave_type_id': policy.id,
                'start_date': date(2026, 8, 3),
                'end_date': date(2026, 8, 5),
            },
            tenant.id,
            employee_user,
        )

        saved = db.session.get(LeaveBalance, balance.id)
        assert float(saved.balance_days) == 2.0
        assert float(saved.reserved_days) == 3.0
        assert request_obj.balance_reserved_at is not None

        with pytest.raises(ValueError, match='Insufficient'):
            create_leave_request(
                {
                    'employee_id': employee.id,
                    'leave_type_id': policy.id,
                    'start_date': date(2026, 8, 10),
                    'end_date': date(2026, 8, 12),
                },
                tenant.id,
                employee_user,
            )

        decide_leave_request(
            request_obj,
            'rejected',
            manager_user,
            'Coverage unavailable',
        )
        saved = db.session.get(LeaveBalance, balance.id)
        assert float(saved.balance_days) == 5.0
        assert float(saved.reserved_days) == 0.0
        assert LeaveLedgerEntry.query.filter_by(
            tenant_id=tenant.id,
            event_type='REQUEST_RESTORED',
        ).count() == 1


def test_future_approved_request_can_be_cancelled_and_restored(
    app,
    tenant,
):
    with app.app_context():
        employee_user, employee = _user_employee(
            tenant.id,
            email='auto-leave@example.test',
            number='AUTO-001',
            first_name='Automatic',
        )
        policy = _policy(
            tenant.id,
            requires_approval=False,
        )
        balance = _opening_balance(
            employee,
            policy,
            year=2027,
        )

        request_obj = create_leave_request(
            {
                'employee_id': employee.id,
                'leave_type_id': policy.id,
                'start_date': date(2027, 2, 1),
                'end_date': date(2027, 2, 2),
            },
            tenant.id,
            employee_user,
        )
        assert request_obj.status == 'approved'

        saved = db.session.get(LeaveBalance, balance.id)
        assert float(saved.balance_days) == 3.0
        assert float(saved.used_days) == 2.0

        cancelled = cancel_leave_request(
            request_obj,
            employee_user,
            'Plans changed',
        )
        saved = db.session.get(LeaveBalance, balance.id)
        assert cancelled.status == 'cancelled'
        assert float(saved.balance_days) == 5.0
        assert float(saved.used_days) == 0.0


def test_carryover_expires_and_manual_adjustment_is_ledgered(
    app,
    tenant,
    admin_user,
):
    admin_id = _identity(admin_user)

    with app.app_context():
        employee = Employee(
            tenant_id=tenant.id,
            employee_number='CAR-001',
            first_name='Carry',
            last_name='Over',
            email='carryover@example.test',
            hire_date=date(2025, 1, 1),
            employment_status='active',
            employment_type='full_time',
        )
        policy = LeaveType(
            tenant_id=tenant.id,
            code='carryover_test',
            name='Carryover test',
            annual_entitlement_days=Decimal('0'),
            accrual_method='monthly',
            entitlement_mode='accrued',
            carryover_allowed=True,
            max_carryover_days=Decimal('5'),
            carryover_expiry_months=1,
        )
        db.session.add_all([employee, policy])
        db.session.flush()
        previous = LeaveBalance(
            tenant_id=tenant.id,
            employee_id=employee.id,
            leave_type_id=policy.id,
            year=2025,
            balance_days=Decimal('4'),
        )
        db.session.add(previous)
        db.session.commit()

        january = run_scheduled_accruals(
            tenant_id=tenant.id,
            as_of_date=date(2026, 1, 15),
        )
        current = LeaveBalance.query.filter_by(
            tenant_id=tenant.id,
            employee_id=employee.id,
            leave_type_id=policy.id,
            year=2026,
        ).one()
        assert january['carryover_entries'] == 1
        assert float(current.balance_days) == 4.0
        assert current.carryover_expires_at == date(2026, 1, 31)

        february = run_scheduled_accruals(
            tenant_id=tenant.id,
            as_of_date=date(2026, 2, 1),
        )
        assert february['expiry_entries'] == 1
        assert float(current.balance_days) == 0.0
        assert float(current.expired_days) == 4.0

        actor = db.session.get(User, admin_id)
        adjusted, entry = adjust_leave_balance(
            current,
            Decimal('2.5'),
            'Approved retention benefit',
            actor=actor,
            effective_date=date(2026, 2, 1),
        )
        assert float(adjusted.balance_days) == 2.5
        assert entry.event_type == 'MANUAL_ADJUSTMENT'
        assert entry.reason == 'Approved retention benefit'

def test_monthly_accrual_waits_for_period_end_and_prorates_new_hire(
    app,
    tenant,
):
    with app.app_context():
        employee = Employee(
            tenant_id=tenant.id,
            employee_number='PRORATE-001',
            first_name='Prorated',
            last_name='Employee',
            email='prorated@example.test',
            hire_date=date(2026, 7, 16),
            employment_status='active',
            employment_type='full_time',
        )
        policy = LeaveType(
            tenant_id=tenant.id,
            code='prorated_annual',
            name='Prorated annual',
            annual_entitlement_days=Decimal('21'),
            accrual_method='monthly',
            entitlement_mode='accrued',
            requires_approval=True,
        )
        db.session.add_all([employee, policy])
        db.session.commit()

        before_period_end = run_scheduled_accruals(
            tenant_id=tenant.id,
            as_of_date=date(2026, 7, 30),
        )
        balance = LeaveBalance.query.filter_by(
            tenant_id=tenant.id,
            employee_id=employee.id,
            leave_type_id=policy.id,
            year=2026,
        ).one()
        assert before_period_end['accrual_entries'] == 0
        assert float(balance.accrued_days) == 0.0

        at_period_end = run_scheduled_accruals(
            tenant_id=tenant.id,
            as_of_date=date(2026, 7, 31),
        )
        assert at_period_end['accrual_entries'] == 1
        assert float(balance.accrued_days) == 0.9

        through_december = run_scheduled_accruals(
            tenant_id=tenant.id,
            as_of_date=date(2026, 12, 31),
        )
        assert through_december['accrual_entries'] == 5
        assert float(balance.accrued_days) == 9.65


def test_balance_scope_ignores_other_employee_filter_for_employee(
    app,
    tenant,
):
    with app.app_context():
        user, employee = _user_employee(
            tenant.id,
            email='balance-owner@example.test',
            number='BAL-OWN',
            first_name='BalanceOwner',
        )
        _, other_employee = _user_employee(
            tenant.id,
            email='balance-other@example.test',
            number='BAL-OTH',
            first_name='BalanceOther',
        )
        policy = _policy(tenant.id)
        own_balance = _opening_balance(employee, policy)
        _opening_balance(other_employee, policy)

        visible = balance_scope_query(
            user,
            LeaveBalance.query.filter_by(
                tenant_id=tenant.id,
            ),
        ).filter(
            LeaveBalance.employee_id == other_employee.id,
        ).all()

        assert visible == []
        own_visible = balance_scope_query(
            user,
            LeaveBalance.query.filter_by(
                tenant_id=tenant.id,
            ),
        ).all()
        assert [item.id for item in own_visible] == [
            own_balance.id,
        ]

def test_event_based_entitlement_is_not_banked_and_caps_each_request(
    app,
    tenant,
):
    with app.app_context():
        employee = Employee(
            tenant_id=tenant.id,
            employee_number='EVENT-001',
            first_name='Event',
            last_name='Employee',
            email='event@example.test',
            hire_date=date(2026, 1, 1),
            employment_status='active',
            employment_type='full_time',
        )
        policy = LeaveType(
            tenant_id=tenant.id,
            code='bereavement_event',
            name='Bereavement event',
            annual_entitlement_days=Decimal('5'),
            accrual_method='annual',
            entitlement_mode='event_based',
            requires_approval=True,
        )
        db.session.add_all([employee, policy])
        db.session.commit()

        result = run_scheduled_accruals(
            tenant_id=tenant.id,
            as_of_date=date(2026, 7, 31),
        )
        assert result['balances_created'] == 0
        assert LeaveBalance.query.filter_by(
            employee_id=employee.id,
            leave_type_id=policy.id,
        ).count() == 0
        assert assert_balance_available(
            employee,
            policy,
            date(2026, 8, 3),
            Decimal('5'),
        ) is None
        with pytest.raises(ValueError, match='per qualifying event'):
            assert_balance_available(
                employee,
                policy,
                date(2026, 8, 3),
                Decimal('6'),
            )


def test_event_balance_repair_zeroes_legacy_allocation(
    app,
    tenant,
):
    with app.app_context():
        employee = Employee(
            tenant_id=tenant.id,
            employee_number='EVENT-LEGACY',
            first_name='Legacy',
            last_name='Event',
            email='legacy-event@example.test',
            hire_date=date(2026, 1, 1),
            employment_status='active',
            employment_type='full_time',
        )
        policy = LeaveType(
            tenant_id=tenant.id,
            code='legacy_maternity',
            name='Legacy maternity',
            annual_entitlement_days=Decimal('90'),
            accrual_method='annual',
            entitlement_mode='event_based',
        )
        db.session.add_all([employee, policy])
        db.session.flush()
        balance = LeaveBalance(
            tenant_id=tenant.id,
            employee_id=employee.id,
            leave_type_id=policy.id,
            year=2026,
            opening_days=Decimal('90'),
            balance_days=Decimal('90'),
        )
        db.session.add(balance)
        db.session.commit()

        preview = repair_event_based_balances(
            tenant_id=tenant.id,
            dry_run=True,
        )
        assert preview['balances_corrected'] == 1
        assert float(balance.balance_days) == 90.0

        applied = repair_event_based_balances(
            tenant_id=tenant.id,
            as_of_date=date(2026, 7, 31),
            dry_run=False,
        )
        assert applied['balances_corrected'] == 1
        assert float(balance.balance_days) == 0.0
        assert float(balance.opening_days) == 0.0
        assert balance.balance_reconciled is True
        repair_entry = LeaveLedgerEntry.query.filter_by(
            tenant_id=tenant.id,
            idempotency_key=f'event-balance-repair:v1:{balance.id}',
        ).one()
        assert float(repair_entry.amount_days) == -90.0


def test_balance_serialization_exposes_formula_components(app, tenant):
    with app.app_context():
        employee = Employee(
            tenant_id=tenant.id,
            employee_number='FORMULA-001',
            first_name='Formula',
            last_name='Employee',
            email='formula@example.test',
            hire_date=date(2026, 1, 1),
            employment_status='active',
            employment_type='full_time',
        )
        policy = _policy(tenant.id)
        db.session.add(employee)
        db.session.flush()
        balance = LeaveBalance(
            tenant_id=tenant.id,
            employee_id=employee.id,
            leave_type_id=policy.id,
            year=2026,
            opening_days=Decimal('10'),
            adjusted_days=Decimal('1'),
            expired_days=Decimal('2'),
            used_days=Decimal('3'),
            reserved_days=Decimal('1'),
            balance_days=Decimal('5'),
        )
        db.session.add(balance)
        db.session.commit()

        data = balance.to_dict()
        assert data['earned_days'] == 9.0
        assert data['posted_days'] == 6.0
        assert data['available_days'] == 5.0
        assert data['balance_reconciled'] is True
