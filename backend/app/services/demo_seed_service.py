import hashlib
import os
import shutil
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

import pyotp
from flask import current_app
from sqlalchemy import delete

from app.extensions import db
from app.models import (
    AccountToken,
    AttendanceRecord,
    AuditLog,
    Department,
    Document,
    EmergencyContact,
    Employee,
    EmployeeOnboardingTask,
    HomepageEssential,
    JobHistory,
    LeaveBalance,
    LeaveLedgerEntry,
    LeaveRequest,
    LeaveType,
    MfaRecoveryCode,
    Notification,
    OnboardingTask,
    OnboardingTemplate,
    OrganizationEvent,
    SignatureArtifact,
    SignatureEvent,
    SignatureProviderEvent,
    SignatureRecipient,
    SignatureReminderRule,
    SignatureRequest,
    Tenant,
    TenantHomepageSettings,
    User,
    UserRole,
)
from app.models.auth_session import AuthSession
from app.services.mfa_service import _encrypt_secret
from app.services.rbac_service import seed_roles_permissions, set_user_roles
from app.utils.security import hash_password


DEMO_NAMESPACE = UUID('0cb9cb40-159d-42fe-a36f-63bedf58a761')
DEMO_TENANT_SLUG = 'kinetic-demo'
DEMO_TENANT_SLUGS = (
    DEMO_TENANT_SLUG,
    'northstar-sandbox',
    'archive-collective',
)
DEMO_EMAIL_DOMAIN = 'kinetic.demo'
DEFAULT_DEMO_PASSWORD = 'KineticDemo2026!'
DEFAULT_DEMO_MFA_SECRET = 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'

DEMO_ACCOUNTS = (
    {
        'key': 'platform',
        'email': 'platform@kinetic.demo',
        'first_name': 'Platform',
        'last_name': 'Administrator',
        'roles': ['SUPER_ADMIN'],
        'tenant_slug': None,
        'employee_key': None,
        'mfa': True,
        'active': True,
    },
    {
        'key': 'owner',
        'email': 'owner@kinetic.demo',
        'first_name': 'Amina',
        'last_name': 'Njoroge',
        'roles': ['ORGANIZATION_OWNER'],
        'tenant_slug': DEMO_TENANT_SLUG,
        'employee_key': 'amina-njoroge',
        'mfa': False,
        'active': True,
    },
    {
        'key': 'consultant',
        'email': 'consultant@kinetic.demo',
        'first_name': 'David',
        'last_name': 'Ochieng',
        'roles': ['HR_CONSULTANT'],
        'tenant_slug': DEMO_TENANT_SLUG,
        'employee_key': 'david-ochieng',
        'mfa': False,
        'active': True,
    },
    {
        'key': 'client-admin',
        'email': 'admin@kinetic.demo',
        'first_name': 'Wanjiku',
        'last_name': 'Kamau',
        'roles': ['CLIENT_ADMIN'],
        'tenant_slug': DEMO_TENANT_SLUG,
        'employee_key': 'wanjiku-kamau',
        'mfa': True,
        'active': True,
    },
    {
        'key': 'manager-growth',
        'email': 'manager@kinetic.demo',
        'first_name': 'Brian',
        'last_name': 'Mutua',
        'roles': ['MANAGER'],
        'tenant_slug': DEMO_TENANT_SLUG,
        'employee_key': 'brian-mutua',
        'mfa': False,
        'active': True,
    },
    {
        'key': 'manager-operations',
        'email': 'manager.ops@kinetic.demo',
        'first_name': 'Faith',
        'last_name': 'Wekesa',
        'roles': ['MANAGER'],
        'tenant_slug': DEMO_TENANT_SLUG,
        'employee_key': 'faith-wekesa',
        'mfa': False,
        'active': True,
    },
    {
        'key': 'employee',
        'email': 'employee@kinetic.demo',
        'first_name': 'Neema',
        'last_name': 'Hassan',
        'roles': ['EMPLOYEE'],
        'tenant_slug': DEMO_TENANT_SLUG,
        'employee_key': 'neema-hassan',
        'mfa': False,
        'active': True,
    },
    {
        'key': 'new-hire',
        'email': 'newhire@kinetic.demo',
        'first_name': 'Kevin',
        'last_name': 'Mwangi',
        'roles': ['EMPLOYEE'],
        'tenant_slug': DEMO_TENANT_SLUG,
        'employee_key': 'kevin-mwangi',
        'mfa': False,
        'active': True,
    },
    {
        'key': 'inactive-user',
        'email': 'inactive@kinetic.demo',
        'first_name': 'John',
        'last_name': 'Kariuki',
        'roles': ['EMPLOYEE'],
        'tenant_slug': DEMO_TENANT_SLUG,
        'employee_key': 'john-kariuki',
        'mfa': False,
        'active': False,
    },
    {
        'key': 'sandbox-admin',
        'email': 'sandbox.admin@kinetic.demo',
        'first_name': 'Maya',
        'last_name': 'Shah',
        'roles': ['CLIENT_ADMIN'],
        'tenant_slug': 'northstar-sandbox',
        'employee_key': None,
        'mfa': True,
        'active': True,
    },
)

PEOPLE = (
    ('amina-njoroge', 'Amina', 'Njoroge', 'Managing Director', 'executive'),
    ('david-ochieng', 'David', 'Ochieng', 'People Operations Lead', 'people'),
    ('wanjiku-kamau', 'Wanjiku', 'Kamau', 'HRIS Administrator', 'people'),
    ('brian-mutua', 'Brian', 'Mutua', 'Growth Manager', 'revenue'),
    ('faith-wekesa', 'Faith', 'Wekesa', 'Operations Manager', 'operations'),
    ('neema-hassan', 'Neema', 'Hassan', 'Account Executive', 'revenue'),
    ('kevin-mwangi', 'Kevin', 'Mwangi', 'Product Designer', 'product'),
    ('john-kariuki', 'John', 'Kariuki', 'Support Specialist', 'success'),
    ('lydia-atieno', 'Lydia', 'Atieno', 'People Partner', 'people'),
    ('samuel-kiptoo', 'Samuel', 'Kiptoo', 'Talent Coordinator', 'people'),
    ('zawadi-mbatha', 'Zawadi', 'Mbatha', 'Product Manager', 'product'),
    ('ian-kibet', 'Ian', 'Kibet', 'UX Researcher', 'product'),
    ('miriam-wairimu', 'Miriam', 'Wairimu', 'Senior Software Engineer', 'engineering'),
    ('peter-odhiambo', 'Peter', 'Odhiambo', 'Backend Engineer', 'engineering'),
    ('grace-chebet', 'Grace', 'Chebet', 'Frontend Engineer', 'engineering'),
    ('ali-noor', 'Ali', 'Noor', 'Quality Engineer', 'engineering'),
    ('carol-muthoni', 'Carol', 'Muthoni', 'Data Analyst', 'engineering'),
    ('james-otieno', 'James', 'Otieno', 'Solutions Architect', 'engineering'),
    ('ruth-kendi', 'Ruth', 'Kendi', 'Sales Development Representative', 'revenue'),
    ('mark-wambua', 'Mark', 'Wambua', 'Account Executive', 'revenue'),
    ('vivian-akinyi', 'Vivian', 'Akinyi', 'Partnerships Manager', 'revenue'),
    ('dennis-korir', 'Dennis', 'Korir', 'Marketing Specialist', 'revenue'),
    ('sharon-moraa', 'Sharon', 'Moraa', 'Content Strategist', 'revenue'),
    ('eric-kimani', 'Eric', 'Kimani', 'Customer Success Manager', 'success'),
    ('naomi-cherono', 'Naomi', 'Cherono', 'Implementation Specialist', 'success'),
    ('allan-maina', 'Allan', 'Maina', 'Customer Support Analyst', 'success'),
    ('mercy-adhiambo', 'Mercy', 'Adhiambo', 'Customer Education Lead', 'success'),
    ('felix-musau', 'Felix', 'Musau', 'Finance Analyst', 'operations'),
    ('rose-wanjiru', 'Rose', 'Wanjiru', 'Payroll Specialist', 'operations'),
    ('george-nyaga', 'George', 'Nyaga', 'Office Coordinator', 'operations'),
    ('esther-naliaka', 'Esther', 'Naliaka', 'Procurement Officer', 'operations'),
    ('paul-mugo', 'Paul', 'Mugo', 'Legal and Compliance Officer', 'operations'),
    ('halima-abdi', 'Halima', 'Abdi', 'Executive Assistant', 'executive'),
    ('nicholas-bett', 'Nicholas', 'Bett', 'Engineering Manager', 'engineering'),
    ('susan-wafula', 'Susan', 'Wafula', 'Technical Writer', 'engineering'),
    ('kelvin-omondi', 'Kelvin', 'Omondi', 'DevOps Engineer', 'engineering'),
    ('beatrice-njeri', 'Beatrice', 'Njeri', 'Revenue Operations Analyst', 'revenue'),
    ('mohamed-said', 'Mohamed', 'Said', 'Customer Success Associate', 'success'),
    ('agnes-jepkoech', 'Agnes', 'Jepkoech', 'People Operations Intern', 'people'),
    ('tony-mwanzia', 'Tony', 'Mwanzia', 'Junior Software Engineer', 'engineering'),
    ('priscilla-nyambura', 'Priscilla', 'Nyambura', 'Product Design Intern', 'product'),
    ('collins-weru', 'Collins', 'Weru', 'Facilities Assistant', 'operations'),
)

DEPARTMENTS = (
    ('executive', 'Executive', 'EXEC'),
    ('people', 'People & Culture', 'PPL'),
    ('product', 'Product & Design', 'PRD'),
    ('engineering', 'Engineering', 'ENG'),
    ('revenue', 'Revenue', 'REV'),
    ('success', 'Customer Success', 'CS'),
    ('operations', 'Finance & Operations', 'OPS'),
)

DEPARTMENT_HEADS = {
    'executive': 'amina-njoroge',
    'people': 'david-ochieng',
    'product': 'zawadi-mbatha',
    'engineering': 'nicholas-bett',
    'revenue': 'brian-mutua',
    'success': 'eric-kimani',
    'operations': 'faith-wekesa',
}

DEPARTMENT_MANAGERS = {
    'executive': None,
    'people': 'david-ochieng',
    'product': 'zawadi-mbatha',
    'engineering': 'nicholas-bett',
    'revenue': 'brian-mutua',
    'success': 'eric-kimani',
    'operations': 'faith-wekesa',
}


class DemoSeedError(RuntimeError):
    pass


def demo_id(key: str):
    return uuid5(DEMO_NAMESPACE, key)


def _reference_date(value: date | str | None) -> date:
    if isinstance(value, date):
        return value
    candidate = value or os.getenv('DEMO_REFERENCE_DATE')
    if candidate:
        try:
            return date.fromisoformat(candidate)
        except ValueError as exc:
            raise DemoSeedError(
                'DEMO_REFERENCE_DATE must use YYYY-MM-DD format'
            ) from exc
    return date.today()


def _assert_demo_environment() -> None:
    if current_app.config.get('ENVIRONMENT') == 'production':
        raise DemoSeedError('Demo data commands are disabled in production')


def _upsert(model, key: str, **values):
    identifier = demo_id(key)
    instance = db.session.get(model, identifier)
    if instance is None:
        instance = model(id=identifier)
        db.session.add(instance)
    for field, value in values.items():
        setattr(instance, field, value)
    return instance


def _assert_unique_identity(model, identifier, **filters):
    instance = model.query.filter_by(**filters).first()
    if instance is not None and str(instance.id) != str(identifier):
        label = ', '.join(f'{key}={value}' for key, value in filters.items())
        raise DemoSeedError(
            f'Demo seed identity conflicts with an existing record ({label}). '
            'Run demo-reset to replace the managed demo environment.'
        )


def _at(reference: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(reference, time(hour=hour, minute=minute))


def _safe_date(year: int, month: int, day: int) -> date:
    try:
        return date(year, month, day)
    except ValueError:
        return date(year, month, 28)


def _business_days(reference: date, count: int) -> list[date]:
    rows = [reference]
    cursor = reference - timedelta(days=1)
    while len(rows) < count:
        if cursor.weekday() < 5:
            rows.append(cursor)
        cursor -= timedelta(days=1)
    return sorted(rows)


def _tenant_upload_root(tenant_id) -> Path:
    return Path(current_app.config['UPLOAD_FOLDER']) / str(tenant_id)


def _write_demo_document(tenant_id, stored_filename: str, content: str):
    folder = _tenant_upload_root(tenant_id) / 'demo-documents'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / stored_filename
    payload = content.encode('utf-8')
    path.write_bytes(payload)
    return {
        'file_path': str(path),
        'size_bytes': len(payload),
        'checksum_sha256': hashlib.sha256(payload).hexdigest(),
    }


def _seed_tenants(reference: date):
    tenant_specs = (
        {
            'slug': DEMO_TENANT_SLUG,
            'name': 'Kinetic Demo Group',
            'legal_name': 'Kinetic Demo Group Limited',
            'country': 'Kenya',
            'industry': 'Technology Services',
            'status': 'active',
            'billing_plan': 'growth',
            'compliance_region': 'Kenya',
        },
        {
            'slug': 'northstar-sandbox',
            'name': 'Northstar Advisory Sandbox',
            'legal_name': 'Northstar Advisory Sandbox Limited',
            'country': 'Kenya',
            'industry': 'Professional Services',
            'status': 'suspended',
            'billing_plan': 'mvp',
            'compliance_region': 'East Africa',
        },
        {
            'slug': 'archive-collective',
            'name': 'Archive Collective',
            'legal_name': 'Archive Collective Limited',
            'country': 'Uganda',
            'industry': 'Creative Services',
            'status': 'archived',
            'billing_plan': 'mvp',
            'compliance_region': 'East Africa',
        },
    )
    tenants = {}
    for index, spec in enumerate(tenant_specs):
        identifier = demo_id(f'tenant:{spec["slug"]}')
        _assert_unique_identity(
            Tenant,
            identifier,
            slug=spec['slug'],
        )
        tenant = _upsert(
            Tenant,
            f'tenant:{spec["slug"]}',
            **spec,
            deleted_at=None,
            leave_setup_completed_at=_at(reference - timedelta(days=60), 9),
            mfa_policy_mode='optional',
            mfa_enrollment_grace_days=14,
            mfa_enforcement_date=None,
            created_at=_at(reference - timedelta(days=365 + (index * 40)), 9),
            updated_at=_at(reference, 7),
        )
        tenants[spec['slug']] = tenant
    db.session.flush()
    return tenants


def _seed_users(tenants, reference: date, password: str, mfa_secret: str):
    password_hash = hash_password(password)
    encrypted_mfa_secret = _encrypt_secret(mfa_secret)
    users = {}
    for index, spec in enumerate(DEMO_ACCOUNTS):
        identifier = demo_id(f'user:{spec["key"]}')
        _assert_unique_identity(
            User,
            identifier,
            email=spec['email'],
        )
        tenant = tenants.get(spec['tenant_slug'])
        user = _upsert(
            User,
            f'user:{spec["key"]}',
            tenant_id=tenant.id if tenant else None,
            email=spec['email'],
            first_name=spec['first_name'],
            last_name=spec['last_name'],
            password_hash=password_hash,
            is_active=spec['active'],
            deleted_at=None,
            email_verified_at=_at(reference - timedelta(days=180), 8),
            last_login_at=(
                _at(reference - timedelta(days=index % 5), 8 + (index % 4))
                if spec['active']
                else None
            ),
            failed_login_attempts=0,
            last_failed_login_at=None,
            locked_until=None,
            mfa_secret_encrypted=(
                encrypted_mfa_secret if spec['mfa'] else None
            ),
            mfa_pending_secret_encrypted=None,
            mfa_enabled_at=(
                _at(reference - timedelta(days=120), 10)
                if spec['mfa']
                else None
            ),
            mfa_last_used_timecode=None,
            mfa_reset_at=None,
            mfa_reset_by_user_id=None,
            created_at=_at(reference - timedelta(days=300 - index), 9),
            updated_at=_at(reference, 7),
        )
        db.session.flush()
        set_user_roles(user, spec['roles'], commit=False)
        users[spec['key']] = user
    db.session.flush()
    return users


def _seed_departments(tenant, reference: date):
    departments = {}
    for index, (key, name, code) in enumerate(DEPARTMENTS):
        department = _upsert(
            Department,
            f'department:{key}',
            tenant_id=tenant.id,
            name=name,
            code=code,
            parent_department_id=None,
            head_employee_id=None,
            deleted_at=None,
            created_at=_at(reference - timedelta(days=340 - index), 9),
            updated_at=_at(reference, 7),
        )
        departments[key] = department
    db.session.flush()
    return departments


def _person_email(key: str) -> str:
    return f'{key.replace("-", ".")}@people.kinetic.demo'


def _seed_employees(tenant, departments, users, reference: date):
    user_by_employee = {
        spec['employee_key']: users[spec['key']]
        for spec in DEMO_ACCOUNTS
        if spec['employee_key'] and spec['tenant_slug'] == DEMO_TENANT_SLUG
    }
    employees = {}
    locations = ('Nairobi', 'Nairobi', 'Remote - Kenya', 'Mombasa', 'Kampala')
    hobbies = ('Reading', 'Running', 'Football', 'Photography', 'Cooking')
    genders = ('woman', 'man', 'woman', 'man', 'non_binary')

    for index, (key, first_name, last_name, title, department_key) in enumerate(PEOPLE, start=1):
        user = user_by_employee.get(key)
        hire_days = 2200 - (index * 31)
        if key == 'kevin-mwangi':
            hire_days = 12
        elif key == 'agnes-jepkoech':
            hire_days = 18
        elif key == 'tony-mwanzia':
            hire_days = 23
        elif key == 'priscilla-nyambura':
            hire_days = 27

        employment_status = 'active'
        employment_type = 'full_time'
        termination_date = None
        if key in {'agnes-jepkoech', 'priscilla-nyambura'}:
            employment_status = 'probation'
            employment_type = 'intern'
        elif key == 'collins-weru':
            employment_status = 'suspended'
        elif key == 'john-kariuki':
            employment_status = 'terminated'
            termination_date = reference - timedelta(days=45)

        birthday = reference + timedelta(days=(index * 4) % 28)
        birth_year = reference.year - (24 + (index % 18))
        date_of_birth = _safe_date(
            birth_year,
            birthday.month,
            birthday.day,
        )
        employee = _upsert(
            Employee,
            f'employee:{key}',
            tenant_id=tenant.id,
            user_id=user.id if user else None,
            employee_number=f'KIN-{index:04d}',
            first_name=first_name,
            last_name=last_name,
            preferred_name=(first_name if index % 4 == 0 else None),
            email=user.email if user else _person_email(key),
            phone=f'+254700{index:06d}',
            date_of_birth=date_of_birth,
            birthday_visibility=(
                'hidden' if index % 13 == 0 else 'colleagues'
            ),
            profile_photo_url=None,
            profile_cover_url=None,
            biography=(
                f'{first_name} supports the {departments[department_key].name} '
                'team and contributes to a practical, people-first culture.'
            ),
            hobbies_json=[hobbies[index % len(hobbies)], hobbies[(index + 2) % len(hobbies)]],
            gender_identity=genders[index % len(genders)],
            gender_self_description=None,
            national_identifier_last4=f'{1000 + index:04d}',
            hire_date=reference - timedelta(days=hire_days),
            termination_date=termination_date,
            employment_status=employment_status,
            employment_type=employment_type,
            job_title=title,
            department_id=departments[department_key].id,
            manager_id=None,
            work_location=locations[index % len(locations)],
            address='Fictional address for demonstration only',
            external_hris_id=f'DEMO-{index:04d}',
            deleted_at=None,
            created_at=_at(reference - timedelta(days=min(hire_days, 730)), 9),
            updated_at=_at(reference, 7),
        )
        employees[key] = employee
    db.session.flush()

    for key, _, _, _, department_key in PEOPLE:
        employee = employees[key]
        manager_key = DEPARTMENT_MANAGERS[department_key]
        if key == 'amina-njoroge':
            manager_key = None
        elif key in DEPARTMENT_HEADS.values():
            manager_key = 'amina-njoroge'
        elif key == 'wanjiku-kamau':
            manager_key = 'david-ochieng'
        employee.manager_id = (
            employees[manager_key].id if manager_key else None
        )

    for department_key, employee_key in DEPARTMENT_HEADS.items():
        departments[department_key].head_employee_id = employees[employee_key].id

    db.session.flush()
    return employees


def _seed_employee_details(tenant, employees, departments, reference: date):
    keys = list(employees)[:12]
    for index, key in enumerate(keys):
        employee = employees[key]
        _upsert(
            EmergencyContact,
            f'emergency-contact:{key}',
            tenant_id=tenant.id,
            employee_id=employee.id,
            name=f'{employee.first_name} Demo Contact',
            relationship='Family member',
            phone=f'+254711{index:06d}',
            email=f'contact.{index + 1}@example.test',
            is_primary=True,
            created_at=_at(reference - timedelta(days=120), 10),
            updated_at=_at(reference, 7),
        )
        _upsert(
            JobHistory,
            f'job-history:{key}:current',
            tenant_id=tenant.id,
            employee_id=employee.id,
            job_title=employee.job_title,
            department_id=employee.department_id,
            manager_id=employee.manager_id,
            start_date=employee.hire_date,
            end_date=None,
            reason='Joined Kinetic Demo Group',
            compensation_band=f'Band {2 + (index % 4)}',
            created_at=_at(reference - timedelta(days=110), 10),
            updated_at=_at(reference, 7),
        )
    db.session.flush()


def _seed_leave(tenant, employees, users, reference: date):
    leave_types = {
        'annual': _upsert(
            LeaveType,
            'leave-type:annual',
            tenant_id=tenant.id,
            code='ANNUAL',
            name='Annual leave',
            annual_entitlement_days=Decimal('21.00'),
            accrual_method='annual',
            entitlement_mode='granted_upfront',
            pay_percentage=Decimal('100.00'),
            eligibility_after_months=0,
            requires_approval=True,
            is_active=True,
            carryover_allowed=True,
            max_carryover_days=Decimal('5.00'),
            carryover_expiry_months=3,
            allow_negative_balance=False,
            minimum_notice_days=3,
            documentation_after_days=None,
            created_at=_at(reference - timedelta(days=300), 9),
            updated_at=_at(reference, 7),
        ),
        'sick': _upsert(
            LeaveType,
            'leave-type:sick',
            tenant_id=tenant.id,
            code='SICK',
            name='Sick leave',
            annual_entitlement_days=Decimal('10.00'),
            accrual_method='annual',
            entitlement_mode='granted_upfront',
            pay_percentage=Decimal('100.00'),
            eligibility_after_months=0,
            requires_approval=True,
            is_active=True,
            carryover_allowed=False,
            max_carryover_days=Decimal('0.00'),
            carryover_expiry_months=None,
            allow_negative_balance=False,
            minimum_notice_days=0,
            documentation_after_days=3,
            created_at=_at(reference - timedelta(days=300), 9),
            updated_at=_at(reference, 7),
        ),
        'compassionate': _upsert(
            LeaveType,
            'leave-type:compassionate',
            tenant_id=tenant.id,
            code='COMP',
            name='Compassionate leave',
            annual_entitlement_days=Decimal('5.00'),
            accrual_method='none',
            entitlement_mode='event_based',
            pay_percentage=Decimal('100.00'),
            eligibility_after_months=0,
            requires_approval=True,
            is_active=True,
            carryover_allowed=False,
            max_carryover_days=Decimal('0.00'),
            carryover_expiry_months=None,
            allow_negative_balance=False,
            minimum_notice_days=0,
            documentation_after_days=None,
            created_at=_at(reference - timedelta(days=300), 9),
            updated_at=_at(reference, 7),
        ),
        'parental': _upsert(
            LeaveType,
            'leave-type:parental',
            tenant_id=tenant.id,
            code='PARENTAL',
            name='Parental leave',
            annual_entitlement_days=Decimal('90.00'),
            accrual_method='none',
            entitlement_mode='event_based',
            pay_percentage=Decimal('100.00'),
            eligibility_after_months=6,
            requires_approval=True,
            is_active=True,
            carryover_allowed=False,
            max_carryover_days=Decimal('0.00'),
            carryover_expiry_months=None,
            allow_negative_balance=False,
            minimum_notice_days=30,
            documentation_after_days=None,
            created_at=_at(reference - timedelta(days=300), 9),
            updated_at=_at(reference, 7),
        ),
    }
    db.session.flush()

    balances = {}
    for index, (key, employee) in enumerate(employees.items(), start=1):
        if employee.employment_status == 'terminated':
            continue
        annual_used = Decimal(str(index % 5))
        sick_used = Decimal(str(index % 3))
        balances[(key, 'annual')] = _upsert(
            LeaveBalance,
            f'leave-balance:{key}:annual:{reference.year}',
            tenant_id=tenant.id,
            employee_id=employee.id,
            leave_type_id=leave_types['annual'].id,
            opening_days=Decimal('21.00'),
            balance_days=Decimal('21.00') - annual_used,
            accrued_days=Decimal('0.00'),
            carried_over_days=Decimal('0.00'),
            adjusted_days=Decimal('0.00'),
            used_days=annual_used,
            reserved_days=Decimal('0.00'),
            expired_days=Decimal('0.00'),
            carryover_remaining_days=Decimal('0.00'),
            carryover_expires_at=None,
            accrual_through_date=reference,
            year=reference.year,
            created_at=_at(reference - timedelta(days=210), 9),
            updated_at=_at(reference, 7),
        )
        balances[(key, 'sick')] = _upsert(
            LeaveBalance,
            f'leave-balance:{key}:sick:{reference.year}',
            tenant_id=tenant.id,
            employee_id=employee.id,
            leave_type_id=leave_types['sick'].id,
            opening_days=Decimal('10.00'),
            balance_days=Decimal('10.00') - sick_used,
            accrued_days=Decimal('0.00'),
            carried_over_days=Decimal('0.00'),
            adjusted_days=Decimal('0.00'),
            used_days=sick_used,
            reserved_days=Decimal('0.00'),
            expired_days=Decimal('0.00'),
            carryover_remaining_days=Decimal('0.00'),
            carryover_expires_at=None,
            accrual_through_date=reference,
            year=reference.year,
            created_at=_at(reference - timedelta(days=210), 9),
            updated_at=_at(reference, 7),
        )
    db.session.flush()

    request_specs = (
        ('neema-pending', 'neema-hassan', 'annual', 12, 14, 'pending', 'manager-growth', 'Client planning break'),
        ('mark-pending', 'mark-wambua', 'annual', 16, 17, 'pending', 'manager-growth', 'Family commitment'),
        ('faith-pending', 'faith-wekesa', 'annual', 20, 22, 'pending', 'owner', 'Quarter-end recovery time'),
        ('vivian-out', 'vivian-akinyi', 'annual', -1, 1, 'approved', 'manager-growth', 'Annual leave'),
        ('allan-out', 'allan-maina', 'sick', 0, 0, 'approved', 'manager-growth', 'Medical appointment'),
        ('miriam-upcoming', 'miriam-wairimu', 'annual', 6, 8, 'approved', 'manager-operations', 'Personal travel'),
        ('rose-upcoming', 'rose-wanjiru', 'annual', 9, 10, 'approved', 'manager-operations', 'Family event'),
        ('ruth-rejected', 'ruth-kendi', 'annual', 24, 25, 'rejected', 'manager-growth', 'Peak campaign period'),
        ('ali-cancelled', 'ali-noor', 'annual', 28, 29, 'cancelled', 'manager-operations', 'Plans changed'),
        ('david-past', 'david-ochieng', 'annual', -40, -38, 'approved', 'owner', 'Rest and recharge'),
    )
    requests = {}
    for index, (
        request_key,
        employee_key,
        leave_key,
        start_offset,
        end_offset,
        status,
        approver_key,
        reason,
    ) in enumerate(request_specs):
        employee = employees[employee_key]
        requester = employee.user or users['consultant']
        approver = users[approver_key]
        start_date = reference + timedelta(days=start_offset)
        end_date = reference + timedelta(days=end_offset)
        total_days = Decimal(str(
            sum(
                1
                for offset in range((end_date - start_date).days + 1)
                if (start_date + timedelta(days=offset)).weekday() < 5
            ) or 1
        ))
        decided_at = None
        if status in {'approved', 'rejected'}:
            decided_at = _at(reference - timedelta(days=max(1, 5 - index)), 14)
        request_obj = _upsert(
            LeaveRequest,
            f'leave-request:{request_key}',
            tenant_id=tenant.id,
            employee_id=employee.id,
            leave_type_id=leave_types[leave_key].id,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            reason=reason,
            status=status,
            requested_by_user_id=requester.id,
            required_approver_id=approver.id,
            approver_id=(approver.id if status in {'approved', 'rejected'} else None),
            approval_route='employee_to_manager',
            balance_reserved_at=(
                _at(reference - timedelta(days=2), 10)
                if status == 'pending'
                else None
            ),
            reserved_carryover_days=Decimal('0.00'),
            decision_notes=(
                'Approved for the demo schedule.'
                if status == 'approved'
                else (
                    'Please choose dates outside the campaign launch.'
                    if status == 'rejected'
                    else None
                )
            ),
            decided_at=decided_at,
            created_at=_at(reference - timedelta(days=12 - index), 9),
            updated_at=_at(reference - timedelta(days=max(0, 4 - index)), 14),
        )
        requests[request_key] = request_obj
        balance = balances.get((employee_key, leave_key))
        if balance is not None:
            if status == 'pending':
                balance.reserved_days = Decimal(balance.reserved_days or 0) + total_days
            elif status == 'approved':
                balance.used_days = Decimal(balance.used_days or 0) + total_days
            balance.balance_days = (
                Decimal(balance.opening_days or 0)
                + Decimal(balance.accrued_days or 0)
                + Decimal(balance.carried_over_days or 0)
                + Decimal(balance.adjusted_days or 0)
                - Decimal(balance.expired_days or 0)
                - Decimal(balance.used_days or 0)
                - Decimal(balance.reserved_days or 0)
            )
    db.session.flush()

    ledger_index = 0
    for (employee_key, leave_key), balance in list(balances.items())[:16]:
        ledger_index += 1
        _upsert(
            LeaveLedgerEntry,
            f'leave-ledger:opening:{employee_key}:{leave_key}:{reference.year}',
            tenant_id=tenant.id,
            employee_id=balance.employee_id,
            leave_type_id=balance.leave_type_id,
            leave_balance_id=balance.id,
            leave_request_id=None,
            actor_user_id=users['consultant'].id,
            event_type='OPENING_BALANCE',
            amount_days=balance.opening_days,
            balance_after_days=balance.balance_days,
            effective_date=date(reference.year, 1, 1),
            year=reference.year,
            idempotency_key=f'demo-opening-{employee_key}-{leave_key}-{reference.year}',
            reason='Deterministic demo opening balance',
            metadata_json={'source': 'demo_seed'},
            created_at=_at(reference - timedelta(days=200 - ledger_index), 9),
            updated_at=_at(reference, 7),
        )
    return leave_types, balances, requests


def _seed_attendance(tenant, employees, reference: date):
    work_days = _business_days(reference, 8)
    rows = 0
    for employee_index, (employee_key, employee) in enumerate(employees.items()):
        if employee.employment_status not in {'active', 'probation'}:
            continue
        for day_index, work_date in enumerate(work_days):
            minute = (employee_index * 7 + day_index * 3) % 25
            check_in = _at(work_date, 8, 15 + minute)
            is_open = (
                employee_key == 'neema-hassan'
                and work_date == reference
            )
            check_out = None if is_open else _at(
                work_date,
                17,
                5 + ((employee_index + day_index) % 35),
            )
            _upsert(
                AttendanceRecord,
                f'attendance:{employee_key}:{day_index}',
                tenant_id=tenant.id,
                employee_id=employee.id,
                work_date=work_date,
                check_in_at=check_in,
                check_out_at=check_out,
                source='self_service',
                notes=(
                    'Open demo session for check-out.'
                    if is_open
                    else None
                ),
                created_at=check_in,
                updated_at=check_out or check_in,
            )
            rows += 1
    return rows


def _seed_documents(tenant, employees, users, reference: date):
    shared_specs = (
        ('employee-handbook', 'Employee Handbook 2026', 'policy', 'employee', 'signed'),
        ('information-security', 'Information Security Policy', 'policy', 'employee', 'pending'),
        ('remote-work', 'Hybrid and Remote Work Guide', 'policy', 'employee', 'not_required'),
        ('manager-playbook', 'Manager Playbook', 'manager_guide', 'manager', 'not_required'),
        ('expense-policy', 'Travel and Expense Policy', 'policy', 'employee', 'signed'),
        ('benefits-guide', 'Benefits and Wellbeing Guide', 'benefits', 'employee', 'not_required'),
        ('safety-guide', 'Workplace Safety Guide', 'policy', 'employee', 'signed'),
        ('code-of-conduct', 'Code of Conduct', 'policy', 'employee', 'signed'),
    )
    document_specs = []
    for spec in shared_specs:
        document_specs.append((*spec, None))

    employee_keys = list(employees)
    for index in range(32):
        employee_key = employee_keys[index]
        employee = employees[employee_key]
        if index < 20:
            document_type = 'contract'
            title = f'Employment Contract — {employee.full_name}'
        elif index < 26:
            document_type = 'identity'
            title = f'Identity Verification — {employee.full_name}'
        else:
            document_type = 'performance'
            title = f'Quarterly Check-in — {employee.full_name}'
        signature_status = (
            'pending' if index in {1, 9, 13, 17} else 'signed'
        )
        document_specs.append((
            f'{document_type}-{employee_key}',
            title,
            document_type,
            'employee' if document_type != 'performance' else 'manager',
            signature_status,
            employee_key,
        ))

    documents = {}
    for index, (
        key,
        title,
        document_type,
        access_level,
        signature_status,
        employee_key,
    ) in enumerate(document_specs, start=1):
        stored_filename = f'demo-{index:02d}-{key}.txt'
        original_filename = f'{key}.txt'
        content = (
            f'{title}\n\n'
            'This is fictional demonstration content generated by Kinetic.\n'
            'It contains no real employee, customer or legal information.\n'
        )
        stored = _write_demo_document(
            tenant.id,
            stored_filename,
            content,
        )
        expiry_date = None
        status = 'active'
        if index in {10, 11, 12}:
            expiry_date = reference + timedelta(days=(index - 9) * 8)
        elif index == 13:
            expiry_date = reference - timedelta(days=5)
            status = 'expired'
        document = _upsert(
            Document,
            f'document:{key}',
            tenant_id=tenant.id,
            employee_id=(
                employees[employee_key].id if employee_key else None
            ),
            uploaded_by_id=users['consultant'].id,
            title=title,
            document_type=document_type,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=stored['file_path'],
            mime_type='text/plain',
            size_bytes=stored['size_bytes'],
            checksum_sha256=stored['checksum_sha256'],
            expiry_date=expiry_date,
            issued_date=reference - timedelta(days=90 + index),
            signature_status=signature_status,
            access_level=access_level,
            status=status,
            version=1,
            deleted_at=None,
            created_at=_at(reference - timedelta(days=80 - (index % 30)), 9),
            updated_at=_at(reference - timedelta(days=index % 6), 11),
        )
        documents[key] = document
    db.session.flush()
    return documents


def _seed_signatures(tenant, documents, employees, users, reference: date):
    pending_request = _upsert(
        SignatureRequest,
        'signature-request:security-policy',
        tenant_id=tenant.id,
        document_id=documents['information-security'].id,
        created_by_id=users['consultant'].id,
        subject='Acknowledge the Information Security Policy',
        message='Please review and acknowledge the updated policy.',
        signing_mode='sequential',
        status='sent',
        current_sequence=1,
        due_at=_at(reference + timedelta(days=5), 17),
        sent_at=_at(reference - timedelta(days=2), 10),
        completed_at=None,
        cancelled_at=None,
        provider='internal',
        provider_request_id=None,
        provider_status=None,
        provider_test_mode=True,
        assurance_level='standard',
        provider_metadata_json={},
        provider_created_at=None,
        provider_downloadable_at=None,
        evidence_completed_at=None,
        evidence_status='not_required',
        evidence_attempts=0,
        evidence_next_attempt_at=None,
        evidence_last_attempt_at=None,
        evidence_locked_at=None,
        evidence_last_error=None,
        evidence_verification_json={},
        created_at=_at(reference - timedelta(days=2), 10),
        updated_at=_at(reference - timedelta(days=2), 10),
    )
    completed_request = _upsert(
        SignatureRequest,
        'signature-request:employee-contract',
        tenant_id=tenant.id,
        document_id=documents['contract-neema-hassan'].id,
        created_by_id=users['consultant'].id,
        subject='Employment contract acknowledgement',
        message='Completed demonstration workflow.',
        signing_mode='parallel',
        status='completed',
        current_sequence=1,
        due_at=_at(reference - timedelta(days=10), 17),
        sent_at=_at(reference - timedelta(days=20), 10),
        completed_at=_at(reference - timedelta(days=14), 15),
        cancelled_at=None,
        provider='internal',
        provider_request_id=None,
        provider_status='completed',
        provider_test_mode=True,
        assurance_level='standard',
        provider_metadata_json={},
        provider_created_at=None,
        provider_downloadable_at=None,
        evidence_completed_at=None,
        evidence_status='not_required',
        evidence_attempts=0,
        evidence_next_attempt_at=None,
        evidence_last_attempt_at=None,
        evidence_locked_at=None,
        evidence_last_error=None,
        evidence_verification_json={},
        created_at=_at(reference - timedelta(days=20), 10),
        updated_at=_at(reference - timedelta(days=14), 15),
    )
    db.session.flush()

    _upsert(
        SignatureRecipient,
        'signature-recipient:security-policy:employee',
        tenant_id=tenant.id,
        signature_request_id=pending_request.id,
        user_id=users['employee'].id,
        employee_id=employees['neema-hassan'].id,
        name=employees['neema-hassan'].full_name,
        email=users['employee'].email,
        role_label='Policy recipient',
        sequence=1,
        status='notified',
        due_at=pending_request.due_at,
        notified_at=pending_request.sent_at,
        viewed_at=None,
        signed_at=None,
        declined_at=None,
        last_reminder_at=None,
        decline_reason=None,
        provider_recipient_id=None,
        provider_status=None,
        provider_metadata_json={},
        created_at=pending_request.created_at,
        updated_at=pending_request.updated_at,
    )
    _upsert(
        SignatureRecipient,
        'signature-recipient:employee-contract:employee',
        tenant_id=tenant.id,
        signature_request_id=completed_request.id,
        user_id=users['employee'].id,
        employee_id=employees['neema-hassan'].id,
        name=employees['neema-hassan'].full_name,
        email=users['employee'].email,
        role_label='Employee',
        sequence=1,
        status='signed',
        due_at=completed_request.due_at,
        notified_at=completed_request.sent_at,
        viewed_at=_at(reference - timedelta(days=15), 10),
        signed_at=completed_request.completed_at,
        declined_at=None,
        last_reminder_at=None,
        decline_reason=None,
        provider_recipient_id=None,
        provider_status='signed',
        provider_metadata_json={},
        created_at=completed_request.created_at,
        updated_at=completed_request.updated_at,
    )
    _upsert(
        SignatureReminderRule,
        'signature-reminder:security-policy',
        tenant_id=tenant.id,
        signature_request_id=pending_request.id,
        first_reminder_after_days=2,
        reminder_interval_days=2,
        escalation_days_before_due=1,
        is_active=True,
        next_run_at=_at(reference + timedelta(days=1), 9),
        created_at=pending_request.created_at,
        updated_at=pending_request.updated_at,
    )


def _seed_onboarding(tenant, employees, users, reference: date):
    template = _upsert(
        OnboardingTemplate,
        'onboarding-template:hybrid-starter',
        tenant_id=tenant.id,
        name='New starter — hybrid team',
        description='A practical first-30-days plan for Kinetic demo hires.',
        is_active=True,
        created_at=_at(reference - timedelta(days=180), 9),
        updated_at=_at(reference, 7),
    )
    contractor_template = _upsert(
        OnboardingTemplate,
        'onboarding-template:contractor',
        tenant_id=tenant.id,
        name='Contractor quick start',
        description='Core access, security and manager alignment tasks.',
        is_active=True,
        created_at=_at(reference - timedelta(days=160), 9),
        updated_at=_at(reference, 7),
    )
    db.session.flush()

    task_specs = (
        ('profile', template, 'Complete your Kinetic profile', 'EMPLOYEE', 0, True),
        ('policies', template, 'Review required workplace policies', 'EMPLOYEE', 1, True),
        ('manager-meeting', template, 'Hold the first manager check-in', 'MANAGER', 2, True),
        ('equipment', template, 'Confirm equipment and system access', 'CLIENT_ADMIN', 0, True),
        ('thirty-day', template, 'Complete the 30-day check-in', 'MANAGER', 30, True),
        ('contractor-access', contractor_template, 'Confirm contractor access', 'CLIENT_ADMIN', 0, True),
        ('contractor-security', contractor_template, 'Complete security orientation', 'EMPLOYEE', 1, True),
    )
    tasks = {}
    for index, (key, parent, title, role, due_days, required) in enumerate(task_specs):
        task = _upsert(
            OnboardingTask,
            f'onboarding-task:{key}',
            tenant_id=tenant.id,
            template_id=parent.id,
            title=title,
            description='Presentation-ready fictional onboarding work.',
            assignee_role=role,
            due_days_after_start=due_days,
            required=required,
            created_at=_at(reference - timedelta(days=150 - index), 9),
            updated_at=_at(reference, 7),
        )
        tasks[key] = task
    db.session.flush()

    hire_keys = ('kevin-mwangi', 'agnes-jepkoech', 'tony-mwanzia')
    for hire_index, employee_key in enumerate(hire_keys):
        employee = employees[employee_key]
        for task_index, task_key in enumerate(
            ('profile', 'policies', 'manager-meeting', 'equipment', 'thirty-day')
        ):
            task = tasks[task_key]
            if task_index < hire_index + 1:
                status = 'completed'
                completed_at = _at(reference - timedelta(days=max(0, 3 - task_index)), 15)
            elif task.due_days_after_start + employee.hire_date.toordinal() < reference.toordinal():
                status = 'overdue'
                completed_at = None
            else:
                status = 'pending'
                completed_at = None
            assigned_to = None
            if task.assignee_role == 'EMPLOYEE' and employee.user_id:
                assigned_to = employee.user_id
            elif task.assignee_role == 'MANAGER':
                assigned_to = users['manager-growth'].id
            elif task.assignee_role == 'CLIENT_ADMIN':
                assigned_to = users['consultant'].id
            _upsert(
                EmployeeOnboardingTask,
                f'onboarding-assignment:{employee_key}:{task_key}',
                tenant_id=tenant.id,
                employee_id=employee.id,
                task_id=task.id,
                assigned_to_user_id=assigned_to,
                status=status,
                due_date=employee.hire_date + timedelta(days=task.due_days_after_start),
                completed_at=completed_at,
                completion_notes=(
                    'Completed during the deterministic demo setup.'
                    if completed_at
                    else None
                ),
                created_at=_at(employee.hire_date, 9),
                updated_at=completed_at or _at(reference, 7),
            )


def _seed_employee_home(tenant, documents, users, reference: date):
    _upsert(
        TenantHomepageSettings,
        'homepage-settings:kinetic-demo',
        tenant_id=tenant.id,
        banner_url=None,
        logo_url=None,
        welcome_message='Welcome to Kinetic Demo Group — move work and people forward.',
        enabled_sections=[
            'birthdays',
            'essentials',
            'people_out_today',
            'events_this_week',
            'new_hires',
            'anniversaries',
            'our_people',
        ],
        section_order=[
            'essentials',
            'people_out_today',
            'events_this_week',
            'new_hires',
            'birthdays',
            'anniversaries',
            'our_people',
        ],
        new_hire_window_days=30,
        birthday_visibility_enabled=True,
        anniversaries_enabled=True,
        people_statistics_enabled=True,
        assistant_enabled=False,
        assistant_url=None,
        created_at=_at(reference - timedelta(days=180), 9),
        updated_at=_at(reference, 7),
    )

    monday = reference - timedelta(days=reference.weekday())
    event_specs = (
        ('all-hands', 'Monthly company all-hands', monday + timedelta(days=1), 10, 'Nairobi Hub', 'all'),
        ('wellbeing', 'Wellbeing and focus hour', monday + timedelta(days=3), 15, 'Online', 'employees'),
        ('manager-roundtable', 'Manager roundtable', monday + timedelta(days=2), 14, 'Meeting Room 3', 'managers'),
        ('customer-story', 'Customer story showcase', monday + timedelta(days=4), 11, 'Online', 'all'),
    )
    for index, (key, title, event_date, hour, location, audience) in enumerate(event_specs):
        starts_at = _at(event_date, hour)
        _upsert(
            OrganizationEvent,
            f'organization-event:{key}',
            tenant_id=tenant.id,
            title=title,
            description='A fictional Kinetic demo event for the employee homepage.',
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
            location=location,
            meeting_url=('https://example.test/demo-meeting' if location == 'Online' else None),
            image_url=None,
            audience=audience,
            status='published',
            created_by_id=users['consultant'].id,
            published_at=_at(reference - timedelta(days=10 - index), 9),
            created_at=_at(reference - timedelta(days=12 - index), 9),
            updated_at=_at(reference - timedelta(days=10 - index), 9),
        )

    essential_keys = (
        ('employee-handbook', 'Employee handbook', 'required'),
        ('information-security', 'Information security', 'required'),
        ('expense-policy', 'Travel and expenses', 'recommended'),
        ('benefits-guide', 'Benefits and wellbeing', 'recommended'),
    )
    for index, (document_key, title, importance) in enumerate(essential_keys):
        _upsert(
            HomepageEssential,
            f'homepage-essential:{document_key}',
            tenant_id=tenant.id,
            document_id=documents[document_key].id,
            display_title=title,
            display_order=index + 1,
            importance=importance,
            is_published=True,
            created_at=_at(reference - timedelta(days=60 - index), 9),
            updated_at=_at(reference, 7),
        )


def _seed_notifications_and_audit(tenant, employees, users, reference: date):
    notification_specs = (
        ('manager-leave', 'manager-growth', '2 leave requests need your decision', 'Review team availability before approving.', 'leave'),
        ('employee-signature', 'employee', 'Information Security Policy requires acknowledgement', 'Please complete the policy task before Friday.', 'signature'),
        ('newhire-onboarding', 'new-hire', 'Your first-week onboarding plan is ready', 'Start with your profile and required policies.', 'onboarding'),
        ('admin-compliance', 'consultant', '3 documents expire within 30 days', 'Open Files to review the compliance queue.', 'compliance'),
    )
    for index, (key, user_key, title, body, notification_type) in enumerate(notification_specs):
        _upsert(
            Notification,
            f'notification:{key}',
            tenant_id=tenant.id,
            user_id=users[user_key].id,
            title=title,
            body=body,
            notification_type=notification_type,
            read_at=(
                _at(reference - timedelta(days=1), 16)
                if index == 3
                else None
            ),
            created_at=_at(reference - timedelta(days=index), 8 + index),
            updated_at=_at(reference - timedelta(days=index), 8 + index),
        )

    audit_specs = (
        ('seed', 'demo.seed', 'Tenant', tenant.id, 'Demo environment created'),
        ('employee-create', 'employee.create', 'Employee', employees['kevin-mwangi'].id, 'Recent hire added'),
        ('leave-submit', 'leave.request', 'LeaveRequest', demo_id('leave-request:neema-pending'), 'Leave request submitted'),
        ('document-upload', 'document.upload', 'Document', demo_id('document:information-security'), 'Policy uploaded'),
        ('signature-send', 'signature.request_send', 'SignatureRequest', demo_id('signature-request:security-policy'), 'Acknowledgement workflow sent'),
        ('onboarding-assign', 'onboarding.assign', 'Employee', employees['kevin-mwangi'].id, 'Onboarding assigned'),
    )
    for index, (key, action, entity_type, entity_id, message) in enumerate(audit_specs):
        _upsert(
            AuditLog,
            f'audit:{key}',
            tenant_id=tenant.id,
            actor_user_id=users['consultant'].id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address='127.0.0.1',
            user_agent='Kinetic deterministic demo seed',
            metadata_json={'message': message, 'source': 'demo_seed'},
            created_at=_at(reference - timedelta(days=6 - index), 9 + index),
            updated_at=_at(reference - timedelta(days=6 - index), 9 + index),
        )


def _configure_tenant_governance(tenants, users):
    primary = tenants[DEMO_TENANT_SLUG]
    primary.organization_owner_user_id = users['owner'].id
    primary.leave_alternate_approver_user_id = users['consultant'].id
    primary.mfa_policy_updated_by_id = users['client-admin'].id
    sandbox = tenants['northstar-sandbox']
    sandbox.organization_owner_user_id = users['sandbox-admin'].id
    db.session.flush()


def demo_manifest(reference: date | str | None = None) -> dict:
    reference_date = _reference_date(reference)
    primary = Tenant.query.filter_by(
        slug=DEMO_TENANT_SLUG,
        deleted_at=None,
    ).first()
    tenant_ids = [
        tenant.id
        for tenant in Tenant.query.filter(
            Tenant.slug.in_(DEMO_TENANT_SLUGS),
            Tenant.deleted_at.is_(None),
        ).all()
    ]
    if not primary:
        return {
            'seeded': False,
            'reference_date': reference_date.isoformat(),
            'tenant_slug': DEMO_TENANT_SLUG,
            'accounts': [
                {
                    'email': account['email'],
                    'roles': account['roles'],
                    'tenant_slug': account['tenant_slug'],
                    'mfa_enabled': account['mfa'],
                    'active': account['active'],
                }
                for account in DEMO_ACCOUNTS
            ],
        }

    primary_id = primary.id
    return {
        'seeded': True,
        'reference_date': reference_date.isoformat(),
        'tenant_id': str(primary_id),
        'tenant_slug': DEMO_TENANT_SLUG,
        'counts': {
            'tenants': len(tenant_ids),
            'users': User.query.filter(
                User.email.like(f'%@{DEMO_EMAIL_DOMAIN}')
            ).count(),
            'employees': Employee.query.filter_by(
                tenant_id=primary_id,
                deleted_at=None,
            ).count(),
            'departments': Department.query.filter_by(
                tenant_id=primary_id,
                deleted_at=None,
            ).count(),
            'documents': Document.query.filter_by(
                tenant_id=primary_id,
                deleted_at=None,
            ).count(),
            'leave_requests': LeaveRequest.query.filter_by(
                tenant_id=primary_id,
            ).count(),
            'attendance_records': AttendanceRecord.query.filter_by(
                tenant_id=primary_id,
            ).count(),
            'onboarding_assignments': EmployeeOnboardingTask.query.filter_by(
                tenant_id=primary_id,
            ).count(),
            'signature_requests': SignatureRequest.query.filter_by(
                tenant_id=primary_id,
            ).count(),
        },
        'accounts': [
            {
                'email': account['email'],
                'roles': account['roles'],
                'tenant_slug': account['tenant_slug'],
                'mfa_enabled': account['mfa'],
                'active': account['active'],
            }
            for account in DEMO_ACCOUNTS
        ],
    }


def _seed_demo_data(
    *,
    reference: date | str | None = None,
    password: str | None = None,
    mfa_secret: str | None = None,
) -> dict:
    _assert_demo_environment()
    reference_date = _reference_date(reference)
    demo_password = password or os.getenv('DEMO_PASSWORD') or DEFAULT_DEMO_PASSWORD
    demo_mfa_secret = (
        mfa_secret
        or os.getenv('DEMO_MFA_SECRET')
        or DEFAULT_DEMO_MFA_SECRET
    )
    if len(demo_password) < 12:
        raise DemoSeedError('DEMO_PASSWORD must contain at least 12 characters')
    try:
        pyotp.TOTP(demo_mfa_secret).now()
    except Exception as exc:
        raise DemoSeedError('DEMO_MFA_SECRET must be valid base32') from exc

    seed_roles_permissions(commit=False)
    tenants = _seed_tenants(reference_date)
    users = _seed_users(
        tenants,
        reference_date,
        demo_password,
        demo_mfa_secret,
    )
    _configure_tenant_governance(tenants, users)
    primary = tenants[DEMO_TENANT_SLUG]
    departments = _seed_departments(primary, reference_date)
    employees = _seed_employees(
        primary,
        departments,
        users,
        reference_date,
    )
    _seed_employee_details(
        primary,
        employees,
        departments,
        reference_date,
    )
    _seed_leave(primary, employees, users, reference_date)
    _seed_attendance(primary, employees, reference_date)
    documents = _seed_documents(
        primary,
        employees,
        users,
        reference_date,
    )
    _seed_signatures(
        primary,
        documents,
        employees,
        users,
        reference_date,
    )
    _seed_onboarding(primary, employees, users, reference_date)
    _seed_employee_home(
        primary,
        documents,
        users,
        reference_date,
    )
    _seed_notifications_and_audit(
        primary,
        employees,
        users,
        reference_date,
    )
    db.session.commit()
    return demo_manifest(reference_date)


def seed_demo_data(
    *,
    reference: date | str | None = None,
    password: str | None = None,
    mfa_secret: str | None = None,
) -> dict:
    try:
        return _seed_demo_data(
            reference=reference,
            password=password,
            mfa_secret=mfa_secret,
        )
    except Exception:
        db.session.rollback()
        raise


def _demo_user_ids(tenant_ids):
    users = User.query.filter(
        User.email.like(f'%@{DEMO_EMAIL_DOMAIN}')
    ).all()
    if tenant_ids:
        users.extend(
            User.query.filter(User.tenant_id.in_(tenant_ids)).all()
        )
    return list({user.id for user in users})


def clear_demo_data() -> dict:
    _assert_demo_environment()
    tenants = Tenant.query.filter(
        Tenant.slug.in_(DEMO_TENANT_SLUGS)
    ).all()
    tenant_ids = [tenant.id for tenant in tenants]
    user_ids = _demo_user_ids(tenant_ids)
    upload_roots = [_tenant_upload_root(tenant_id) for tenant_id in tenant_ids]

    for tenant in tenants:
        tenant.organization_owner_user_id = None
        tenant.leave_alternate_approver_user_id = None
        tenant.mfa_policy_updated_by_id = None
    if user_ids:
        User.query.filter(User.id.in_(user_ids)).update(
            {User.mfa_reset_by_user_id: None},
            synchronize_session=False,
        )
    if tenant_ids:
        Department.query.filter(
            Department.tenant_id.in_(tenant_ids)
        ).update(
            {Department.head_employee_id: None},
            synchronize_session=False,
        )
        Employee.query.filter(
            Employee.tenant_id.in_(tenant_ids)
        ).update(
            {
                Employee.manager_id: None,
                Employee.department_id: None,
            },
            synchronize_session=False,
        )
    db.session.flush()

    tenant_models = (
        SignatureArtifact,
        SignatureProviderEvent,
        SignatureEvent,
        SignatureReminderRule,
        SignatureRecipient,
        SignatureRequest,
        HomepageEssential,
        OrganizationEvent,
        TenantHomepageSettings,
        EmployeeOnboardingTask,
        OnboardingTask,
        OnboardingTemplate,
        AttendanceRecord,
        LeaveLedgerEntry,
        LeaveRequest,
        LeaveBalance,
        LeaveType,
        Document,
        EmergencyContact,
        JobHistory,
        Notification,
        AuditLog,
    )
    if tenant_ids:
        for model in tenant_models:
            db.session.execute(
                delete(model).where(model.tenant_id.in_(tenant_ids))
            )
        db.session.execute(
            delete(Employee).where(Employee.tenant_id.in_(tenant_ids))
        )
        db.session.execute(
            delete(Department).where(Department.tenant_id.in_(tenant_ids))
        )

    if user_ids:
        db.session.execute(
            delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id.in_(user_ids))
        )
        db.session.execute(
            delete(AccountToken).where(AccountToken.user_id.in_(user_ids))
        )
        db.session.execute(
            delete(AuthSession).where(AuthSession.user_id.in_(user_ids))
        )
        db.session.execute(
            delete(UserRole).where(UserRole.user_id.in_(user_ids))
        )
        db.session.execute(
            delete(User).where(User.id.in_(user_ids))
        )
    if tenant_ids:
        db.session.execute(
            delete(Tenant).where(Tenant.id.in_(tenant_ids))
        )
    db.session.commit()
    db.session.expunge_all()

    for root in upload_roots:
        shutil.rmtree(root, ignore_errors=True)
    return {
        'cleared': True,
        'tenants_removed': len(tenant_ids),
        'users_removed': len(user_ids),
    }


def reset_demo_data(
    *,
    reference: date | str | None = None,
    password: str | None = None,
    mfa_secret: str | None = None,
) -> dict:
    clear_demo_data()
    return seed_demo_data(
        reference=reference,
        password=password,
        mfa_secret=mfa_secret,
    )


def demo_mfa_code(
    email: str,
    *,
    mfa_secret: str | None = None,
) -> str:
    _assert_demo_environment()
    normalized = email.strip().lower()
    allowed = {
        account['email']
        for account in DEMO_ACCOUNTS
        if account['mfa']
    }
    if normalized not in allowed:
        raise DemoSeedError(
            'MFA codes are available only for privileged demo accounts'
        )
    secret = (
        mfa_secret
        or os.getenv('DEMO_MFA_SECRET')
        or DEFAULT_DEMO_MFA_SECRET
    )
    return pyotp.TOTP(secret).now()
