import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import false

from app.extensions import db
from app.models import (
    Employee,
    LeaveBalance,
    LeaveLedgerEntry,
    LeaveRequest,
    LeaveType,
    Tenant,
)
from app.models.base import utcnow
from app.services.audit_service import log_event


DAY = Decimal('0.01')
ACTIVE_EMPLOYMENT_STATUSES = {'active', 'probation'}
NON_BALANCE_ENTITLEMENT_MODES = {'unlimited', 'event_based'}


def quantize_days(value):
    return Decimal(value or 0).quantize(
        DAY,
        rounding=ROUND_HALF_UP,
    )


def add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def month_end(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def monthly_entitlement_amount(entitlement, month):
    entitlement = quantize_days(entitlement)
    standard = quantize_days(entitlement / Decimal('12'))
    if month == 12:
        return max(
            Decimal('0'),
            quantize_days(
                entitlement - (standard * Decimal('11')),
            ),
        )
    return standard


def prorated_monthly_entitlement(
    policy,
    employee,
    year,
    month,
):
    period_start = date(year, month, 1)
    period_end = month_end(year, month)
    active_from = max(
        period_start,
        eligibility_date(policy, employee),
    )
    active_until = period_end
    if employee.termination_date:
        active_until = min(
            active_until,
            employee.termination_date,
        )
    if active_from > active_until:
        return Decimal('0')

    period_days = Decimal(
        (period_end - period_start).days + 1,
    )
    eligible_days = Decimal(
        (active_until - active_from).days + 1,
    )
    scheduled = monthly_entitlement_amount(
        policy.annual_entitlement_days,
        month,
    )
    return quantize_days(
        scheduled * eligible_days / period_days,
    )


def eligibility_date(policy, employee):
    return add_months(
        employee.hire_date,
        int(policy.eligibility_after_months or 0),
    )


def uses_balance(leave_type):
    return (
        leave_type.entitlement_mode
        not in NON_BALANCE_ENTITLEMENT_MODES
    )


def validate_event_entitlement(leave_type, total_days):
    if leave_type.entitlement_mode != 'event_based':
        return

    requested = quantize_days(total_days)
    maximum = quantize_days(leave_type.annual_entitlement_days)
    if maximum > 0 and requested > maximum:
        raise ValueError(
            f'{leave_type.name} permits up to {maximum} days '
            'per qualifying event'
        )


def get_or_create_balance(
    tenant_id,
    employee_id,
    leave_type_id,
    year,
    *,
    lock=False,
):
    query = LeaveBalance.query.filter_by(
        tenant_id=tenant_id,
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        year=year,
    )
    if lock:
        query = query.with_for_update()
    balance = query.first()
    if balance is not None:
        return balance, False

    balance = LeaveBalance(
        tenant_id=tenant_id,
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        year=year,
    )
    db.session.add(balance)
    db.session.flush()
    return balance, True


def record_ledger_entry(
    balance,
    event_type,
    amount_days,
    effective_date,
    idempotency_key,
    *,
    actor_user_id=None,
    leave_request_id=None,
    reason=None,
    metadata=None,
):
    existing = LeaveLedgerEntry.query.filter_by(
        tenant_id=balance.tenant_id,
        idempotency_key=idempotency_key,
    ).first()
    if existing is not None:
        return existing, False

    entry = LeaveLedgerEntry(
        tenant_id=balance.tenant_id,
        employee_id=balance.employee_id,
        leave_type_id=balance.leave_type_id,
        leave_balance_id=balance.id,
        leave_request_id=leave_request_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        amount_days=quantize_days(amount_days),
        balance_after_days=quantize_days(balance.balance_days),
        effective_date=effective_date,
        year=balance.year,
        idempotency_key=idempotency_key,
        reason=reason,
        metadata_json=metadata or {},
    )
    db.session.add(entry)
    db.session.flush()
    return entry, True


def _consume_carryover(balance, amount):
    available = quantize_days(balance.carryover_remaining_days)
    consumed = min(available, quantize_days(amount))
    balance.carryover_remaining_days = available - consumed
    return consumed


def _restore_carryover(balance, amount):
    amount = quantize_days(amount)
    if amount <= 0:
        return
    maximum = max(
        Decimal('0'),
        quantize_days(balance.carried_over_days)
        - quantize_days(balance.expired_days),
    )
    balance.carryover_remaining_days = min(
        maximum,
        quantize_days(balance.carryover_remaining_days) + amount,
    )


def assert_balance_available(employee, leave_type, start_date, total_days):
    validate_event_entitlement(leave_type, total_days)
    if not uses_balance(leave_type):
        return None

    balance = LeaveBalance.query.filter_by(
        tenant_id=employee.tenant_id,
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        year=start_date.year,
    ).first()
    if balance is None:
        raise ValueError(
            'Opening balances have not been initialized for '
            'this leave policy'
        )

    available = quantize_days(balance.available_days)
    requested = quantize_days(total_days)
    if (
        not leave_type.allow_negative_balance
        and available < requested
    ):
        raise ValueError(
            f'Insufficient leave balance: {available} days available'
        )
    return balance


def reserve_request_balance(leave_request, actor_user_id=None):
    leave_type = leave_request.leave_type
    if not uses_balance(leave_type):
        return None
    if leave_request.balance_reserved_at is not None:
        return None

    balance, _ = get_or_create_balance(
        leave_request.tenant_id,
        leave_request.employee_id,
        leave_request.leave_type_id,
        leave_request.start_date.year,
        lock=True,
    )
    requested = quantize_days(leave_request.total_days)
    available = quantize_days(balance.available_days)
    if (
        not leave_type.allow_negative_balance
        and available < requested
    ):
        raise ValueError(
            f'Insufficient leave balance: {available} days available'
        )

    reserved_carryover = _consume_carryover(balance, requested)
    balance.balance_days = available - requested
    balance.reserved_days = (
        quantize_days(balance.reserved_days) + requested
    )
    leave_request.balance_reserved_at = utcnow()
    leave_request.reserved_carryover_days = reserved_carryover

    return record_ledger_entry(
        balance,
        'REQUEST_RESERVED',
        -requested,
        leave_request.start_date,
        f'request-reserved:{leave_request.id}',
        actor_user_id=actor_user_id,
        leave_request_id=leave_request.id,
        metadata={
            'reserved_carryover_days': float(reserved_carryover),
        },
    )[0]


def approve_request_balance(leave_request, actor_user_id=None):
    leave_type = leave_request.leave_type
    if not uses_balance(leave_type):
        return None

    balance, _ = get_or_create_balance(
        leave_request.tenant_id,
        leave_request.employee_id,
        leave_request.leave_type_id,
        leave_request.start_date.year,
        lock=True,
    )
    requested = quantize_days(leave_request.total_days)

    if leave_request.balance_reserved_at is not None:
        balance.reserved_days = max(
            Decimal('0'),
            quantize_days(balance.reserved_days) - requested,
        )
        balance.used_days = (
            quantize_days(balance.used_days) + requested
        )
        amount = Decimal('0')
    else:
        available = quantize_days(balance.available_days)
        if (
            not leave_type.allow_negative_balance
            and available < requested
        ):
            raise ValueError(
                f'Insufficient leave balance: '
                f'{available} days available'
            )
        leave_request.reserved_carryover_days = _consume_carryover(
            balance,
            requested,
        )
        balance.balance_days = available - requested
        balance.used_days = (
            quantize_days(balance.used_days) + requested
        )
        amount = -requested

    return record_ledger_entry(
        balance,
        'REQUEST_APPROVED',
        amount,
        leave_request.start_date,
        f'request-approved:{leave_request.id}',
        actor_user_id=actor_user_id,
        leave_request_id=leave_request.id,
        metadata={
            'finalized_reservation': (
                leave_request.balance_reserved_at is not None
            ),
        },
    )[0]


def restore_request_balance(
    leave_request,
    *,
    actor_user_id=None,
    reason,
):
    leave_type = leave_request.leave_type
    if not uses_balance(leave_type):
        return None

    balance, _ = get_or_create_balance(
        leave_request.tenant_id,
        leave_request.employee_id,
        leave_request.leave_type_id,
        leave_request.start_date.year,
        lock=True,
    )
    requested = quantize_days(leave_request.total_days)
    restored = Decimal('0')

    if (
        leave_request.status == 'pending'
        and leave_request.balance_reserved_at is not None
    ):
        balance.reserved_days = max(
            Decimal('0'),
            quantize_days(balance.reserved_days) - requested,
        )
        balance.balance_days = (
            quantize_days(balance.balance_days) + requested
        )
        restored = requested
        leave_request.balance_reserved_at = None
    elif leave_request.status == 'approved':
        balance.used_days = max(
            Decimal('0'),
            quantize_days(balance.used_days) - requested,
        )
        balance.balance_days = (
            quantize_days(balance.balance_days) + requested
        )
        restored = requested

    if restored <= 0:
        return None

    _restore_carryover(
        balance,
        leave_request.reserved_carryover_days,
    )
    return record_ledger_entry(
        balance,
        'REQUEST_RESTORED',
        restored,
        date.today(),
        f'request-restored:{leave_request.id}:{reason}',
        actor_user_id=actor_user_id,
        leave_request_id=leave_request.id,
        reason=reason,
        metadata={
            'restored_carryover_days': float(
                leave_request.reserved_carryover_days or 0,
            ),
        },
    )[0]


def record_request_cancelled(leave_request, actor_user_id=None, notes=None):
    if not uses_balance(leave_request.leave_type):
        return None

    balance = LeaveBalance.query.filter_by(
        tenant_id=leave_request.tenant_id,
        employee_id=leave_request.employee_id,
        leave_type_id=leave_request.leave_type_id,
        year=leave_request.start_date.year,
    ).first()
    if balance is None:
        return None

    return record_ledger_entry(
        balance,
        'REQUEST_CANCELLED',
        Decimal('0'),
        date.today(),
        f'request-cancelled:{leave_request.id}',
        actor_user_id=actor_user_id,
        leave_request_id=leave_request.id,
        reason=notes,
    )[0]


def adjust_leave_balance(
    balance,
    amount_days,
    reason,
    *,
    actor,
    effective_date=None,
):
    amount = quantize_days(amount_days)
    if amount == 0:
        raise ValueError('Balance adjustment must be non-zero')
    if not reason or not reason.strip():
        raise ValueError('A balance adjustment reason is required')

    locked = LeaveBalance.query.filter_by(
        id=balance.id,
        tenant_id=balance.tenant_id,
    ).with_for_update().one()
    policy = locked.leave_type
    available = quantize_days(locked.available_days)
    if (
        amount < 0
        and not policy.allow_negative_balance
        and available + amount < 0
    ):
        raise ValueError(
            f'Adjustment would exceed the available '
            f'balance of {available} days'
        )

    if amount < 0:
        _consume_carryover(locked, -amount)

    locked.adjusted_days = (
        quantize_days(locked.adjusted_days) + amount
    )
    locked.balance_days = available + amount
    effective = effective_date or date.today()
    entry, _ = record_ledger_entry(
        locked,
        'MANUAL_ADJUSTMENT',
        amount,
        effective,
        f'adjustment:{locked.id}:{utcnow().isoformat()}',
        actor_user_id=actor.id,
        reason=reason.strip(),
    )
    log_event(
        'leave.balance_adjusted',
        'LeaveBalance',
        locked.id,
        tenant_id=locked.tenant_id,
        metadata={
            'amount_days': float(amount),
            'reason': reason.strip(),
            'ledger_entry_id': str(entry.id),
        },
    )
    db.session.commit()
    return locked, entry


def _credit(
    balance,
    amount,
    *,
    bucket,
    event_type,
    effective_date,
    idempotency_key,
    actor_user_id=None,
    reason=None,
    metadata=None,
):
    amount = quantize_days(amount)
    if amount <= 0:
        return None, False

    existing = LeaveLedgerEntry.query.filter_by(
        tenant_id=balance.tenant_id,
        idempotency_key=idempotency_key,
    ).first()
    if existing is not None:
        return existing, False

    if bucket == 'opening_days':
        balance.opening_days = (
            quantize_days(balance.opening_days) + amount
        )
    elif bucket == 'accrued_days':
        balance.accrued_days = (
            quantize_days(balance.accrued_days) + amount
        )
    elif bucket == 'carried_over_days':
        balance.carried_over_days = (
            quantize_days(balance.carried_over_days) + amount
        )
        balance.carryover_remaining_days = (
            quantize_days(balance.carryover_remaining_days) + amount
        )
    else:
        raise ValueError(f'Unsupported balance bucket: {bucket}')

    balance.balance_days = (
        quantize_days(balance.balance_days) + amount
    )
    return record_ledger_entry(
        balance,
        event_type,
        amount,
        effective_date,
        idempotency_key,
        actor_user_id=actor_user_id,
        reason=reason,
        metadata=metadata,
    )


def _baseline_existing_balance(balance, as_of_date):
    entry = LeaveLedgerEntry.query.filter_by(
        tenant_id=balance.tenant_id,
        leave_balance_id=balance.id,
    ).first()
    if entry is not None:
        return False

    record_ledger_entry(
        balance,
        'BASELINE_IMPORT',
        quantize_days(balance.balance_days),
        as_of_date,
        f'baseline:{balance.id}',
        reason='Balance imported when the allocation ledger was enabled',
        metadata={
            'opening_days': float(balance.opening_days or 0),
            'accrued_days': float(balance.accrued_days or 0),
            'used_days': float(balance.used_days or 0),
        },
    )
    if balance.accrual_through_date is None:
        balance.accrual_through_date = month_end(
            as_of_date.year,
            as_of_date.month,
        )
    return True


def initialize_balance_for_policy(
    balance,
    policy,
    employee,
    as_of_date,
    *,
    actor_user_id=None,
    overwrite_unused=False,
):
    existing_entry = LeaveLedgerEntry.query.filter_by(
        tenant_id=balance.tenant_id,
        leave_balance_id=balance.id,
    ).first()
    existing_numbers = any(
        quantize_days(value) != 0
        for value in (
            balance.opening_days,
            balance.accrued_days,
            balance.carried_over_days,
            balance.adjusted_days,
            balance.used_days,
            balance.reserved_days,
            balance.expired_days,
            balance.balance_days,
        )
    )
    if existing_entry is not None:
        return 'skipped'
    if existing_numbers:
        _baseline_existing_balance(balance, as_of_date)
        return 'updated'

    eligible_on = eligibility_date(policy, employee)
    if employee.hire_date > as_of_date or eligible_on > as_of_date:
        balance.accrual_through_date = as_of_date
        return 'updated'

    entitlement = quantize_days(policy.annual_entitlement_days)
    if policy.entitlement_mode in {
        'unlimited',
        'manual',
        'event_based',
    }:
        balance.accrual_through_date = as_of_date
        return 'updated'

    if (
        policy.accrual_method == 'monthly'
        or policy.entitlement_mode == 'accrued'
    ):
        processed_through = None
        for month in range(1, as_of_date.month + 1):
            period_end = month_end(as_of_date.year, month)
            if period_end > as_of_date:
                continue
            amount = prorated_monthly_entitlement(
                policy,
                employee,
                as_of_date.year,
                month,
            )
            if amount <= 0:
                continue
            _credit(
                balance,
                amount,
                bucket='accrued_days',
                event_type='ACCRUAL',
                effective_date=period_end,
                idempotency_key=(
                    f'accrual:{employee.id}:{policy.id}:'
                    f'{as_of_date.year}-{month:02d}'
                ),
                actor_user_id=actor_user_id,
                metadata={
                    'source': 'opening_initialization',
                    'prorated': (
                        amount
                        != monthly_entitlement_amount(
                            entitlement,
                            month,
                        )
                    ),
                },
            )
            processed_through = period_end
        if processed_through:
            balance.accrual_through_date = processed_through
        return 'updated'

    _credit(
        balance,
        entitlement,
        bucket='opening_days',
        event_type='OPENING_BALANCE',
        effective_date=max(
            eligible_on,
            date(as_of_date.year, 1, 1),
        ),
        idempotency_key=(
            f'opening:{employee.id}:{policy.id}:{as_of_date.year}'
        ),
        actor_user_id=actor_user_id,
    )
    balance.accrual_through_date = as_of_date
    return 'updated'


def _apply_carryover(
    balance,
    previous_balance,
    policy,
    employee,
    as_of_date,
    actor_user_id,
):
    if not policy.carryover_allowed:
        return False
    key = (
        f'carryover:{employee.id}:{policy.id}:{as_of_date.year}'
    )
    if LeaveLedgerEntry.query.filter_by(
        tenant_id=balance.tenant_id,
        idempotency_key=key,
    ).first():
        return False

    available = max(
        Decimal('0'),
        quantize_days(previous_balance.balance_days),
    )
    maximum = quantize_days(policy.max_carryover_days)
    amount = min(available, maximum)
    if amount <= 0:
        return False

    _, created = _credit(
        balance,
        amount,
        bucket='carried_over_days',
        event_type='CARRYOVER',
        effective_date=date(as_of_date.year, 1, 1),
        idempotency_key=key,
        actor_user_id=actor_user_id,
        metadata={
            'source_balance_id': str(previous_balance.id),
            'source_year': previous_balance.year,
        },
    )
    expiry_months = policy.carryover_expiry_months
    if created and expiry_months is not None:
        balance.carryover_expires_at = (
            add_months(
                date(as_of_date.year, 1, 1),
                int(expiry_months),
            )
            - timedelta(days=1)
        )
    return created


def _expire_carryover(balance, as_of_date, actor_user_id):
    expires_at = balance.carryover_expires_at
    remaining = quantize_days(balance.carryover_remaining_days)
    if (
        not expires_at
        or as_of_date <= expires_at
        or remaining <= 0
    ):
        return False

    key = f'carryover-expiry:{balance.id}:{expires_at.isoformat()}'
    if LeaveLedgerEntry.query.filter_by(
        tenant_id=balance.tenant_id,
        idempotency_key=key,
    ).first():
        return False

    balance.carryover_remaining_days = Decimal('0')
    balance.expired_days = (
        quantize_days(balance.expired_days) + remaining
    )
    balance.balance_days = (
        quantize_days(balance.balance_days) - remaining
    )
    record_ledger_entry(
        balance,
        'EXPIRY',
        -remaining,
        expires_at,
        key,
        actor_user_id=actor_user_id,
        reason='Unused carryover expired',
    )
    return True


def _accrue_policy_through(
    balance,
    policy,
    employee,
    as_of_date,
    actor_user_id,
):
    eligible_on = eligibility_date(policy, employee)
    if eligible_on > as_of_date:
        return 0

    entitlement = quantize_days(policy.annual_entitlement_days)
    mode = policy.entitlement_mode
    if mode in {'unlimited', 'manual', 'event_based'}:
        return 0

    created = 0
    if policy.accrual_method == 'monthly' or mode == 'accrued':
        for month in range(1, as_of_date.month + 1):
            period_end = month_end(as_of_date.year, month)
            if period_end > as_of_date:
                continue
            if (
                balance.accrual_through_date
                and period_end <= balance.accrual_through_date
            ):
                continue

            amount = prorated_monthly_entitlement(
                policy,
                employee,
                as_of_date.year,
                month,
            )
            if amount <= 0:
                continue
            _, was_created = _credit(
                balance,
                amount,
                bucket='accrued_days',
                event_type='ACCRUAL',
                effective_date=period_end,
                idempotency_key=(
                    f'accrual:{employee.id}:{policy.id}:'
                    f'{as_of_date.year}-{month:02d}'
                ),
                actor_user_id=actor_user_id,
                metadata={
                    'frequency': 'monthly',
                    'prorated': (
                        amount
                        != monthly_entitlement_amount(
                            entitlement,
                            month,
                        )
                    ),
                },
            )
            created += int(was_created)
            balance.accrual_through_date = period_end
        return created

    if (
        balance.accrual_through_date
        and balance.accrual_through_date.year >= as_of_date.year
    ):
        return 0

    effective = max(
        eligible_on,
        date(as_of_date.year, 1, 1),
    )
    _, was_created = _credit(
        balance,
        entitlement,
        bucket='opening_days',
        event_type='ACCRUAL',
        effective_date=effective,
        idempotency_key=(
            f'annual-grant:{employee.id}:{policy.id}:'
            f'{as_of_date.year}'
        ),
        actor_user_id=actor_user_id,
        metadata={'frequency': 'annual'},
    )
    balance.accrual_through_date = effective
    return int(was_created)


def run_scheduled_accruals(
    *,
    as_of_date=None,
    tenant_id=None,
    actor=None,
    commit=True,
):
    as_of = as_of_date or date.today()
    tenant_query = Tenant.query.filter(
        Tenant.status == 'active',
        Tenant.deleted_at.is_(None),
    )
    if tenant_id:
        tenant_query = tenant_query.filter(Tenant.id == tenant_id)
    tenants = tenant_query.all()
    if tenant_id and not tenants:
        raise ValueError('Organization was not found')

    result = {
        'as_of_date': as_of.isoformat(),
        'tenants': 0,
        'balances_created': 0,
        'accrual_entries': 0,
        'carryover_entries': 0,
        'expiry_entries': 0,
    }
    actor_user_id = getattr(actor, 'id', None)

    for tenant in tenants:
        result['tenants'] += 1
        employees = Employee.query.filter(
            Employee.tenant_id == tenant.id,
            Employee.deleted_at.is_(None),
            Employee.employment_status.in_(
                ACTIVE_EMPLOYMENT_STATUSES,
            ),
            Employee.hire_date <= as_of,
        ).all()
        policies = LeaveType.query.filter(
            LeaveType.tenant_id == tenant.id,
            LeaveType.is_active.is_(True),
        ).all()

        for employee in employees:
            for policy in policies:
                if policy.entitlement_mode in {
                    'unlimited',
                    'manual',
                    'event_based',
                }:
                    continue
                balance, created = get_or_create_balance(
                    tenant.id,
                    employee.id,
                    policy.id,
                    as_of.year,
                )
                result['balances_created'] += int(created)

                previous = LeaveBalance.query.filter_by(
                    tenant_id=tenant.id,
                    employee_id=employee.id,
                    leave_type_id=policy.id,
                    year=as_of.year - 1,
                ).first()
                if previous and _apply_carryover(
                    balance,
                    previous,
                    policy,
                    employee,
                    as_of,
                    actor_user_id,
                ):
                    result['carryover_entries'] += 1

                if _expire_carryover(
                    balance,
                    as_of,
                    actor_user_id,
                ):
                    result['expiry_entries'] += 1

                result['accrual_entries'] += _accrue_policy_through(
                    balance,
                    policy,
                    employee,
                    as_of,
                    actor_user_id,
                )

        log_event(
            'leave.accrual_run',
            'Tenant',
            tenant.id,
            tenant_id=tenant.id,
            metadata={
                'as_of_date': as_of.isoformat(),
            },
            actor=actor,
        )

    if commit:
        db.session.commit()
    return result


def repair_event_based_balances(
    *,
    tenant_id=None,
    as_of_date=None,
    actor=None,
    dry_run=True,
    commit=True,
):
    effective = as_of_date or date.today()
    query = LeaveBalance.query.join(LeaveType).filter(
        LeaveType.entitlement_mode == 'event_based',
    )
    if tenant_id:
        query = query.filter(LeaveBalance.tenant_id == tenant_id)

    balances = query.all()
    result = {
        'dry_run': dry_run,
        'balances_scanned': len(balances),
        'balances_corrected': 0,
        'request_reservations_cleared': 0,
    }
    actor_user_id = getattr(actor, 'id', None)

    for balance in balances:
        before = {
            name: float(getattr(balance, name) or 0)
            for name in (
                'opening_days',
                'accrued_days',
                'carried_over_days',
                'adjusted_days',
                'used_days',
                'reserved_days',
                'expired_days',
                'carryover_remaining_days',
                'balance_days',
            )
        }
        if not any(before.values()):
            continue

        result['balances_corrected'] += 1
        if dry_run:
            continue

        delta = -quantize_days(balance.balance_days)
        for name in before:
            setattr(balance, name, Decimal('0'))
        balance.carryover_expires_at = None
        balance.accrual_through_date = effective
        record_ledger_entry(
            balance,
            'MANUAL_ADJUSTMENT',
            delta,
            effective,
            f'event-balance-repair:v1:{balance.id}',
            actor_user_id=actor_user_id,
            reason=(
                'Converted event-based entitlement from a banked '
                'balance to a per-event allowance'
            ),
            metadata={
                'repair_version': 1,
                'before': before,
            },
        )

    request_query = LeaveRequest.query.join(LeaveType).filter(
        LeaveType.entitlement_mode == 'event_based',
        LeaveRequest.balance_reserved_at.is_not(None),
    )
    if tenant_id:
        request_query = request_query.filter(
            LeaveRequest.tenant_id == tenant_id,
        )
    requests = request_query.all()
    result['request_reservations_cleared'] = len(requests)
    if not dry_run:
        for request_obj in requests:
            request_obj.balance_reserved_at = None
            request_obj.reserved_carryover_days = Decimal('0')

        affected_tenants = {
            balance.tenant_id for balance in balances
        } | {request_obj.tenant_id for request_obj in requests}
        for affected_tenant_id in affected_tenants:
            log_event(
                'leave.event_balances_repaired',
                'Tenant',
                affected_tenant_id,
                tenant_id=affected_tenant_id,
                metadata={
                    **result,
                    'effective_date': effective.isoformat(),
                },
                actor=actor,
            )

        if commit:
            db.session.commit()

    return result


def balance_scope_query(user, query):
    if user.has_any_role(
        {
            'SUPER_ADMIN',
            'CLIENT_ADMIN',
            'HR_CONSULTANT',
            'ORGANIZATION_OWNER',
        }
    ):
        return query
    if not user.employee_profile:
        return query.filter(false())
    return query.filter(
        LeaveBalance.employee_id == user.employee_profile.id
    )


def ledger_scope_query(user, query):
    if user.has_any_role(
        {
            'SUPER_ADMIN',
            'CLIENT_ADMIN',
            'HR_CONSULTANT',
            'ORGANIZATION_OWNER',
        }
    ):
        return query
    if not user.employee_profile:
        return query.filter(false())
    return query.filter(
        LeaveLedgerEntry.employee_id == user.employee_profile.id
    )
