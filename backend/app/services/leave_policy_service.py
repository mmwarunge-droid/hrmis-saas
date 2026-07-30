import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Employee,
    LeaveBalance,
    LeaveType,
    Role,
    Tenant,
    User,
    UserRole,
)
from app.models.base import utcnow
from app.services.audit_service import log_event
from app.services.rbac_service import seed_roles_permissions


CONFIGURE_ROLES = {
    'SUPER_ADMIN',
    'CLIENT_ADMIN',
    'HR_CONSULTANT',
    'ORGANIZATION_OWNER',
}
SUBMIT_FOR_OTHERS_ROLES = {
    'SUPER_ADMIN',
    'CLIENT_ADMIN',
    'HR_CONSULTANT',
}

STANDARD_POLICY_PACK = [
    {
        'code': 'annual_leave',
        'name': 'Annual leave',
        'annual_entitlement_days': Decimal('21'),
        'accrual_method': 'monthly',
        'entitlement_mode': 'accrued',
        'pay_percentage': Decimal('100'),
        'eligibility_after_months': 0,
        'requires_approval': True,
        'carryover_allowed': True,
        'max_carryover_days': Decimal('5'),
        'allow_negative_balance': False,
        'minimum_notice_days': 7,
        'documentation_after_days': None,
    },
    {
        'code': 'sick_leave_full_pay',
        'name': 'Sick leave — full pay',
        'annual_entitlement_days': Decimal('7'),
        'accrual_method': 'annual',
        'entitlement_mode': 'granted_upfront',
        'pay_percentage': Decimal('100'),
        'eligibility_after_months': 2,
        'requires_approval': True,
        'carryover_allowed': False,
        'max_carryover_days': Decimal('0'),
        'allow_negative_balance': False,
        'minimum_notice_days': 0,
        'documentation_after_days': 2,
    },
    {
        'code': 'sick_leave_half_pay',
        'name': 'Sick leave — half pay',
        'annual_entitlement_days': Decimal('7'),
        'accrual_method': 'annual',
        'entitlement_mode': 'granted_upfront',
        'pay_percentage': Decimal('50'),
        'eligibility_after_months': 2,
        'requires_approval': True,
        'carryover_allowed': False,
        'max_carryover_days': Decimal('0'),
        'allow_negative_balance': False,
        'minimum_notice_days': 0,
        'documentation_after_days': 2,
    },
    {
        'code': 'maternity_leave',
        'name': 'Maternity leave & pay',
        'annual_entitlement_days': Decimal('90'),
        'accrual_method': 'annual',
        'entitlement_mode': 'event_based',
        'pay_percentage': Decimal('100'),
        'eligibility_after_months': 0,
        'requires_approval': True,
        'carryover_allowed': False,
        'max_carryover_days': Decimal('0'),
        'allow_negative_balance': False,
        'minimum_notice_days': 30,
        'documentation_after_days': 0,
    },
    {
        'code': 'paternity_leave',
        'name': 'Paternity leave',
        'annual_entitlement_days': Decimal('14'),
        'accrual_method': 'annual',
        'entitlement_mode': 'event_based',
        'pay_percentage': Decimal('100'),
        'eligibility_after_months': 0,
        'requires_approval': True,
        'carryover_allowed': False,
        'max_carryover_days': Decimal('0'),
        'allow_negative_balance': False,
        'minimum_notice_days': 14,
        'documentation_after_days': 0,
    },
    {
        'code': 'pre_adoptive_leave',
        'name': 'Pre-adoptive leave',
        'annual_entitlement_days': Decimal('30'),
        'accrual_method': 'annual',
        'entitlement_mode': 'event_based',
        'pay_percentage': Decimal('100'),
        'eligibility_after_months': 0,
        'requires_approval': True,
        'carryover_allowed': False,
        'max_carryover_days': Decimal('0'),
        'allow_negative_balance': False,
        'minimum_notice_days': 14,
        'documentation_after_days': 0,
    },
    {
        'code': 'bereavement',
        'name': 'Bereavement',
        'annual_entitlement_days': Decimal('5'),
        'accrual_method': 'annual',
        'entitlement_mode': 'event_based',
        'pay_percentage': Decimal('100'),
        'eligibility_after_months': 0,
        'requires_approval': True,
        'carryover_allowed': False,
        'max_carryover_days': Decimal('0'),
        'allow_negative_balance': False,
        'minimum_notice_days': 0,
        'documentation_after_days': None,
    },
    {
        'code': 'study_leave',
        'name': 'Study leave',
        'annual_entitlement_days': Decimal('5'),
        'accrual_method': 'annual',
        'entitlement_mode': 'granted_upfront',
        'pay_percentage': Decimal('100'),
        'eligibility_after_months': 3,
        'requires_approval': True,
        'carryover_allowed': False,
        'max_carryover_days': Decimal('0'),
        'allow_negative_balance': False,
        'minimum_notice_days': 14,
        'documentation_after_days': 0,
    },
    {
        'code': 'birthday_benefit',
        'name': 'Birthday benefit',
        'annual_entitlement_days': Decimal('1'),
        'accrual_method': 'annual',
        'entitlement_mode': 'event_based',
        'pay_percentage': Decimal('100'),
        'eligibility_after_months': 0,
        'requires_approval': True,
        'carryover_allowed': False,
        'max_carryover_days': Decimal('0'),
        'allow_negative_balance': False,
        'minimum_notice_days': 3,
        'documentation_after_days': None,
    },
    {
        'code': 'charity_day',
        'name': 'Charity day',
        'annual_entitlement_days': Decimal('1'),
        'accrual_method': 'annual',
        'entitlement_mode': 'granted_upfront',
        'pay_percentage': Decimal('100'),
        'eligibility_after_months': 0,
        'requires_approval': True,
        'carryover_allowed': False,
        'max_carryover_days': Decimal('0'),
        'allow_negative_balance': False,
        'minimum_notice_days': 7,
        'documentation_after_days': None,
    },
    {
        'code': 'unpaid_leave',
        'name': 'Unpaid leave',
        'annual_entitlement_days': Decimal('0'),
        'accrual_method': 'none',
        'entitlement_mode': 'unlimited',
        'pay_percentage': Decimal('0'),
        'eligibility_after_months': 0,
        'requires_approval': True,
        'carryover_allowed': False,
        'max_carryover_days': Decimal('0'),
        'allow_negative_balance': True,
        'minimum_notice_days': 7,
        'documentation_after_days': None,
    },
    {
        'code': 'work_from_anywhere',
        'name': 'Work from anywhere',
        'annual_entitlement_days': Decimal('23'),
        'accrual_method': 'annual',
        'entitlement_mode': 'granted_upfront',
        'pay_percentage': Decimal('100'),
        'eligibility_after_months': 0,
        'requires_approval': True,
        'carryover_allowed': False,
        'max_carryover_days': Decimal('0'),
        'allow_negative_balance': False,
        'minimum_notice_days': 7,
        'documentation_after_days': None,
    },
]


def can_configure_leave(user) -> bool:
    return user.has_any_role(CONFIGURE_ROLES)


def can_submit_for_others(user) -> bool:
    return user.has_any_role(SUBMIT_FOR_OTHERS_ROLES)


def _serialize_user(user):
    if not user:
        return None
    employee = user.employee_profile
    return {
        'id': str(user.id),
        'full_name': user.full_name,
        'email': user.email,
        'roles': user.role_names,
        'employee_id': str(employee.id) if employee else None,
        'job_title': employee.job_title if employee else None,
    }


def _eligible_governance_users(tenant_id):
    return (
        User.query.join(Employee, Employee.user_id == User.id)
        .filter(
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            Employee.deleted_at.is_(None),
            Employee.employment_status.in_(['active', 'probation']),
        )
        .order_by(User.first_name.asc(), User.last_name.asc())
        .all()
    )


def standard_policy_pack():
    return [
        {
            key: (
                float(value)
                if isinstance(value, Decimal)
                else value
            )
            for key, value in item.items()
        }
        for item in STANDARD_POLICY_PACK
    ]


def _merge_policy_overrides(overrides):
    indexed = {
        item['code']: item
        for item in overrides or []
    }
    result = []
    for default in STANDARD_POLICY_PACK:
        merged = dict(default)
        merged.update(indexed.get(default['code'], {}))
        result.append(merged)
    return result


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(
        value.day,
        calendar.monthrange(year, month)[1],
    )
    return date(year, month, day)


def _rounded(value):
    return Decimal(value).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP,
    )


def allocation_for(policy, employee, as_of_date):
    if employee.hire_date > as_of_date:
        return Decimal('0')

    eligibility_date = _add_months(
        employee.hire_date,
        int(policy.eligibility_after_months or 0),
    )
    if eligibility_date > as_of_date:
        return Decimal('0')

    entitlement = Decimal(
        policy.annual_entitlement_days or 0,
    )
    mode = policy.entitlement_mode

    if mode in {'unlimited', 'manual'}:
        return Decimal('0')

    if policy.accrual_method == 'monthly' or mode == 'accrued':
        start = max(
            eligibility_date,
            date(as_of_date.year, 1, 1),
        )
        months = (
            (as_of_date.year - start.year) * 12
            + as_of_date.month
            - start.month
            + 1
        )
        months = max(0, min(months, 12))
        return min(
            entitlement,
            _rounded(entitlement / Decimal('12') * months),
        )

    return _rounded(entitlement)


def initialize_leave_balances(
    tenant_id,
    *,
    year=None,
    as_of_date=None,
    overwrite_unused=False,
):
    as_of = as_of_date or date.today()
    resolved_year = year or as_of.year
    if as_of.year != resolved_year:
        as_of = date(resolved_year, 12, 31)

    employees = Employee.query.filter(
        Employee.tenant_id == tenant_id,
        Employee.deleted_at.is_(None),
        Employee.employment_status.in_(['active', 'probation']),
    ).all()
    policies = LeaveType.query.filter_by(
        tenant_id=tenant_id,
        is_active=True,
    ).all()

    created = 0
    updated = 0
    skipped = 0

    for employee in employees:
        for policy in policies:
            allocation = allocation_for(
                policy,
                employee,
                as_of,
            )
            balance = LeaveBalance.query.filter_by(
                tenant_id=tenant_id,
                employee_id=employee.id,
                leave_type_id=policy.id,
                year=resolved_year,
            ).first()
            if balance is None:
                balance = LeaveBalance(
                    tenant_id=tenant_id,
                    employee_id=employee.id,
                    leave_type_id=policy.id,
                    year=resolved_year,
                    accrued_days=allocation,
                    used_days=Decimal('0'),
                    balance_days=allocation,
                )
                db.session.add(balance)
                created += 1
                continue

            used = Decimal(balance.used_days or 0)
            if used > 0 and not overwrite_unused:
                skipped += 1
                continue
            if not overwrite_unused and (
                Decimal(balance.accrued_days or 0) != 0
                or Decimal(balance.balance_days or 0) != 0
            ):
                skipped += 1
                continue

            balance.accrued_days = allocation
            balance.balance_days = allocation - used
            updated += 1

    log_event(
        'leave.balances_initialized',
        'Tenant',
        tenant_id,
        tenant_id=tenant_id,
        metadata={
            'year': resolved_year,
            'as_of_date': as_of.isoformat(),
            'created': created,
            'updated': updated,
            'skipped': skipped,
        },
    )
    return {
        'year': resolved_year,
        'as_of_date': as_of.isoformat(),
        'created': created,
        'updated': updated,
        'skipped': skipped,
    }


def _refresh_setup_completion(tenant):
    active_policy_exists = LeaveType.query.filter_by(
        tenant_id=tenant.id,
        is_active=True,
    ).first() is not None
    governance_ready = bool(
        tenant.organization_owner_user_id
        and tenant.leave_alternate_approver_user_id
    )
    tenant.leave_setup_completed_at = (
        tenant.leave_setup_completed_at or utcnow()
        if active_policy_exists and governance_ready
        else None
    )


def apply_standard_policy_pack(
    tenant_id,
    actor,
    *,
    overrides=None,
    initialize_balances=True,
    as_of_date=None,
):
    if not can_configure_leave(actor):
        raise PermissionError(
            'Only organization owners and HR administrators '
            'can configure leave policies'
        )

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant or tenant.deleted_at is not None:
        raise ValueError('Organization was not found')

    configured = []
    for item in _merge_policy_overrides(overrides):
        code = item['code']
        policy = LeaveType.query.filter_by(
            tenant_id=tenant_id,
            code=code,
        ).first()
        if policy is None:
            policy = LeaveType.query.filter(
                LeaveType.tenant_id == tenant_id,
                db.func.lower(LeaveType.name)
                == item['name'].lower(),
            ).first()
        if policy is None:
            policy = LeaveType(
                tenant_id=tenant_id,
                code=code,
                name=item['name'],
            )
            db.session.add(policy)
        else:
            policy.code = code

        for field in [
            'name',
            'annual_entitlement_days',
            'accrual_method',
            'entitlement_mode',
            'pay_percentage',
            'eligibility_after_months',
            'requires_approval',
            'carryover_allowed',
            'max_carryover_days',
            'allow_negative_balance',
            'minimum_notice_days',
            'documentation_after_days',
        ]:
            setattr(policy, field, item[field])
        policy.is_active = True
        configured.append(policy)

    db.session.flush()
    balance_result = None
    if initialize_balances:
        balance_result = initialize_leave_balances(
            tenant_id,
            as_of_date=as_of_date,
        )

    _refresh_setup_completion(tenant)
    log_event(
        'leave.policy_pack_applied',
        'Tenant',
        tenant.id,
        tenant_id=tenant.id,
        metadata={
            'policy_codes': [item.code for item in configured],
            'balances_initialized': initialize_balances,
        },
    )
    db.session.commit()
    return configured, balance_result


def _ensure_owner_role(user, actor):
    seed_roles_permissions(commit=False)
    role = Role.query.filter_by(
        name='ORGANIZATION_OWNER',
    ).one()
    existing = UserRole.query.filter_by(
        user_id=user.id,
        role_id=role.id,
    ).first()
    if existing is None:
        db.session.add(
            UserRole(
                tenant_id=user.tenant_id,
                user_id=user.id,
                role_id=role.id,
                assigned_by_id=actor.id,
            )
        )


def _remove_owner_role(user):
    if not user:
        return
    role = Role.query.filter_by(
        name='ORGANIZATION_OWNER',
    ).first()
    if role:
        UserRole.query.filter_by(
            user_id=user.id,
            role_id=role.id,
        ).delete(synchronize_session=False)


def configure_leave_governance(
    tenant_id,
    actor,
    owner_user_id,
    alternate_user_id,
):
    if not can_configure_leave(actor):
        raise PermissionError(
            'Only organization owners and HR administrators '
            'can configure leave governance'
        )
    if str(owner_user_id) == str(alternate_user_id):
        raise ValueError(
            'The organization owner and alternate approver '
            'must be different people'
        )

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant or tenant.deleted_at is not None:
        raise ValueError('Organization was not found')

    candidates = _eligible_governance_users(tenant_id)
    candidate_map = {
        str(user.id): user
        for user in candidates
    }
    owner = candidate_map.get(str(owner_user_id))
    alternate = candidate_map.get(str(alternate_user_id))
    if not owner:
        raise ValueError(
            'organization_owner_user_id must be an active '
            'employee account in this organization'
        )
    if not alternate:
        raise ValueError(
            'alternate_approver_user_id must be an active '
            'employee account in this organization'
        )

    previous_owner = tenant.organization_owner
    if (
        previous_owner
        and str(previous_owner.id) != str(owner.id)
    ):
        _remove_owner_role(previous_owner)

    _ensure_owner_role(owner, actor)
    tenant.organization_owner_user_id = owner.id
    tenant.leave_alternate_approver_user_id = alternate.id
    db.session.flush()
    _refresh_setup_completion(tenant)

    log_event(
        'leave.governance_configured',
        'Tenant',
        tenant.id,
        tenant_id=tenant.id,
        metadata={
            'organization_owner_user_id': str(owner.id),
            'alternate_approver_user_id': str(alternate.id),
        },
    )
    db.session.commit()
    return tenant


def leave_setup_status(tenant_id, user):
    tenant = db.session.get(Tenant, tenant_id)
    if not tenant or tenant.deleted_at is not None:
        raise ValueError('Organization was not found')

    year = date.today().year
    active_policies = LeaveType.query.filter_by(
        tenant_id=tenant_id,
        is_active=True,
    ).order_by(LeaveType.name.asc()).all()
    eligible_employees = Employee.query.filter(
        Employee.tenant_id == tenant_id,
        Employee.deleted_at.is_(None),
        Employee.employment_status.in_(['active', 'probation']),
    ).count()
    balance_count = LeaveBalance.query.filter_by(
        tenant_id=tenant_id,
        year=year,
    ).count()

    current_employee = None
    if (
        user.employee_profile
        and str(user.employee_profile.tenant_id) == str(tenant_id)
    ):
        current_employee = user.employee_profile

    current_balance_count = 0
    if current_employee:
        current_balance_count = LeaveBalance.query.filter_by(
            tenant_id=tenant_id,
            employee_id=current_employee.id,
            year=year,
        ).count()

    owner = tenant.organization_owner
    alternate = tenant.leave_alternate_approver
    missing = []
    if not current_employee:
        missing.append({
            'code': 'employee_profile',
            'title': 'Link your employee profile',
            'description': (
                'A user account must be linked to an employee '
                'record before that person can request time off.'
            ),
        })
    if not active_policies:
        missing.append({
            'code': 'leave_policies',
            'title': 'Configure leave policies',
            'description': (
                'Apply the standard policy pack or create at '
                'least one active leave policy.'
            ),
        })
    if not owner:
        missing.append({
            'code': 'organization_owner',
            'title': 'Appoint the business owner',
            'description': (
                'HR and client-administrator requests require '
                'an organization owner approver.'
            ),
        })
    if not alternate:
        missing.append({
            'code': 'alternate_approver',
            'title': 'Appoint an alternate approver',
            'description': (
                'The business owner needs an independent '
                'approver for their own requests.'
            ),
        })
    if active_policies and current_employee and not current_balance_count:
        missing.append({
            'code': 'opening_balances',
            'title': 'Initialize opening balances',
            'description': (
                'Create the current-year allocation before '
                'submitting a balance-controlled request.'
            ),
        })

    candidates = [
        _serialize_user(candidate)
        for candidate in _eligible_governance_users(tenant_id)
    ]

    return {
        'tenant_id': str(tenant.id),
        'year': year,
        'can_configure': can_configure_leave(user),
        'can_submit_for_others': can_submit_for_others(user),
        'ready_to_request': not missing,
        'missing_requirements': missing,
        'current_employee': (
            current_employee.to_dict()
            if current_employee
            else None
        ),
        'organization_owner': _serialize_user(owner),
        'alternate_approver': _serialize_user(alternate),
        'governance_candidates': candidates,
        'active_policy_count': len(active_policies),
        'eligible_employee_count': eligible_employees,
        'balance_count': balance_count,
        'policies': [
            policy.to_dict()
            for policy in active_policies
        ],
        'standard_pack': standard_policy_pack(),
        'setup_completed_at': (
            tenant.leave_setup_completed_at.isoformat()
            if tenant.leave_setup_completed_at
            else None
        ),
    }


def find_fallback_owner(tenant_id, exclude_user_id=None):
    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return None
    candidate_ids = [
        tenant.organization_owner_user_id,
        tenant.leave_alternate_approver_user_id,
    ]
    for candidate_id in candidate_ids:
        if not candidate_id:
            continue
        if exclude_user_id and str(candidate_id) == str(exclude_user_id):
            continue
        candidate = User.query.filter(
            User.id == candidate_id,
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        ).first()
        if candidate:
            return candidate
    return None


def active_policy_query(tenant_id):
    return LeaveType.query.filter(
        LeaveType.tenant_id == tenant_id,
        LeaveType.is_active.is_(True),
        or_(
            LeaveType.entitlement_mode == 'unlimited',
            LeaveType.annual_entitlement_days >= 0,
        ),
    )
