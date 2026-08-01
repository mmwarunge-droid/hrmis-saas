from collections import Counter
from datetime import date, datetime, time, timedelta

from flask import Blueprint, request, send_file, url_for
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (
    Document,
    Employee,
    HomepageEssential,
    LeaveRequest,
    OrganizationEvent,
    Tenant,
    TenantHomepageSettings,
)
from app.models.base import utcnow
from app.models.employee_home import DEFAULT_HOME_SECTIONS
from app.schemas.employee_home_schema import (
    EmployeeSelfProfileSchema,
    HomepageEssentialCreateSchema,
    HomepageEssentialUpdateSchema,
    HomepageSettingsUpdateSchema,
    OrganizationEventCreateSchema,
    OrganizationEventUpdateSchema,
)
from app.services.audit_service import log_event
from app.services.document_service import can_access_document
from app.utils.homepage_branding_storage import (
    delete_employee_profile_image,
    delete_homepage_branding_image,
    employee_profile_image_path,
    homepage_branding_path,
    save_employee_profile_image,
    save_homepage_branding_image,
)
from app.utils.response import fail, success

employee_home_bp = Blueprint('employee_home', __name__)

ADMIN_ROLES = {'CLIENT_ADMIN', 'ORGANIZATION_OWNER', 'SUPER_ADMIN'}
PEOPLE_STATS_MIN_GROUP = 3


def _resolve_tenant_id(explicit_tenant_id=None):
    if current_user.has_role('SUPER_ADMIN'):
        return explicit_tenant_id or request.args.get('tenant_id')
    return current_user.tenant_id


def _require_tenant(explicit_tenant_id=None):
    tenant_id = _resolve_tenant_id(explicit_tenant_id)
    if not tenant_id:
        return None, fail('TENANT_REQUIRED', 'An organization must be selected', 422)
    if (
        explicit_tenant_id
        and not current_user.has_role('SUPER_ADMIN')
        and str(current_user.tenant_id) != str(explicit_tenant_id)
    ):
        return None, fail('FORBIDDEN', 'You cannot manage another organization', 403)
    tenant = Tenant.query.filter_by(id=tenant_id, deleted_at=None).first()
    if not tenant:
        return None, fail('TENANT_NOT_FOUND', 'Organization not found', 404)
    return tenant, None


def _require_home_admin(tenant_id):
    tenant, error = _require_tenant(tenant_id)
    if error:
        return None, error
    if not current_user.has_any_role(ADMIN_ROLES):
        return None, fail(
            'FORBIDDEN',
            'Only client administrators and organization owners can manage the employee homepage',
            403,
        )
    return tenant, None


def _settings_for(tenant_id, *, create=False):
    settings = TenantHomepageSettings.query.filter_by(tenant_id=tenant_id).first()
    if settings is None:
        # SQLAlchemy column defaults are applied during INSERT/flush, not when a
        # transient model instance is constructed. The employee-home GET path
        # intentionally returns an unsaved default settings object, so every
        # runtime default must be explicit here.
        settings = TenantHomepageSettings(
            tenant_id=tenant_id,
            welcome_message='Glad you are here.',
            enabled_sections=list(DEFAULT_HOME_SECTIONS),
            section_order=list(DEFAULT_HOME_SECTIONS),
            new_hire_window_days=30,
            birthday_visibility_enabled=True,
            anniversaries_enabled=True,
            people_statistics_enabled=True,
            assistant_enabled=False,
        )
        if create:
            db.session.add(settings)
    return settings


def _managed_branding_filename(url, tenant_id):
    fragment = f'/employee-home/branding/{tenant_id}/'
    if not url or fragment not in url:
        return None
    return url.rsplit('/', 1)[-1]


def _managed_profile_filename(url, employee_id):
    fragment = f'/employee-home/profile-images/{employee_id}/'
    if not url or fragment not in url:
        return None
    return url.rsplit('/', 1)[-1]


def _next_occurrence(month, day, today):
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            candidate = date(year, 2, 28)
        if candidate >= today:
            return candidate
    return None


def _public_person(employee):
    return {
        'id': str(employee.id),
        'full_name': employee.full_name,
        'preferred_name': employee.preferred_name,
        'job_title': employee.job_title,
        'department_name': employee.department.name if employee.department else None,
        'work_location': employee.work_location,
        'profile_photo_url': employee.profile_photo_url,
    }


def _birthday_items(employees, today, enabled):
    if not enabled:
        return []
    items = []
    for employee in employees:
        if not employee.date_of_birth or employee.birthday_visibility != 'colleagues':
            continue
        occurrence = _next_occurrence(
            employee.date_of_birth.month,
            employee.date_of_birth.day,
            today,
        )
        if occurrence is None or occurrence > today + timedelta(days=30):
            continue
        items.append({
            **_public_person(employee),
            'date': occurrence.isoformat(),
            'is_today': occurrence == today,
        })
    return sorted(items, key=lambda item: item['date'])[:8]


def _anniversary_items(employees, today, enabled):
    if not enabled:
        return []
    items = []
    for employee in employees:
        if not employee.hire_date:
            continue
        occurrence = _next_occurrence(
            employee.hire_date.month,
            employee.hire_date.day,
            today,
        )
        if occurrence is None or occurrence > today + timedelta(days=30):
            continue
        years = occurrence.year - employee.hire_date.year
        if years < 1:
            continue
        items.append({
            **_public_person(employee),
            'date': occurrence.isoformat(),
            'years': years,
            'is_today': occurrence == today,
        })
    return sorted(items, key=lambda item: item['date'])[:8]


def _count_dimension(values, labels=None):
    counts = Counter(value for value in values if value)
    rows = []
    for value, count in counts.most_common():
        if count < PEOPLE_STATS_MIN_GROUP:
            continue
        rows.append({
            'key': value,
            'label': labels.get(value, value) if labels else value,
            'count': count,
        })
    return rows


def _people_statistics(employees, enabled):
    if not enabled:
        return None

    gender_labels = {
        'woman': 'Women',
        'man': 'Men',
        'non_binary': 'Non-binary',
        'self_described': 'Self-described',
    }
    genders = [
        employee.gender_identity
        for employee in employees
        if employee.gender_identity not in {None, 'prefer_not_to_say'}
    ]
    locations = [employee.work_location for employee in employees]
    departments = [
        employee.department.name
        for employee in employees
        if employee.department is not None
    ]
    hobbies = []
    for employee in employees:
        hobbies.extend(employee.hobbies_json or [])

    return {
        'total_employees': len(employees),
        'gender': _count_dimension(genders, gender_labels),
        'locations': _count_dimension(locations),
        'departments': _count_dimension(departments),
        'hobbies': _count_dimension(hobbies),
        'minimum_group_size': PEOPLE_STATS_MIN_GROUP,
    }


def _self_profile(employee):
    return {
        **employee.to_dict(),
        'date_of_birth': employee.date_of_birth.isoformat() if employee.date_of_birth else None,
        'birthday_visibility': employee.birthday_visibility,
        'gender_identity': employee.gender_identity,
        'gender_self_description': employee.gender_self_description,
        'department_name': (
            employee.department.name if employee.department else None
        ),
    }


@employee_home_bp.get('/employee-home')
@jwt_required()
def employee_home():
    tenant, error = _require_tenant()
    if error:
        return error

    settings = _settings_for(tenant.id)
    today = date.today()
    now = datetime.utcnow()
    week_start = today - timedelta(days=today.weekday())
    week_start_at = datetime.combine(week_start, time.min)
    week_end_at = week_start_at + timedelta(days=7)

    employees = (
        Employee.query.options(selectinload(Employee.department))
        .filter(
            Employee.tenant_id == tenant.id,
            Employee.deleted_at.is_(None),
            Employee.employment_status.in_(['active', 'probation']),
        )
        .order_by(Employee.last_name.asc(), Employee.first_name.asc())
        .all()
    )
    event_audiences = ['all', 'employees']
    if current_user.has_role('MANAGER') or current_user.has_any_role(ADMIN_ROLES):
        event_audiences.append('managers')
    events = (
        OrganizationEvent.query.filter(
            OrganizationEvent.tenant_id == tenant.id,
            OrganizationEvent.status == 'published',
            OrganizationEvent.audience.in_(event_audiences),
            OrganizationEvent.starts_at < week_end_at,
            or_(
                OrganizationEvent.ends_at.is_(None),
                OrganizationEvent.ends_at >= week_start_at,
            ),
        )
        .order_by(OrganizationEvent.starts_at.asc())
        .limit(8)
        .all()
    )

    essential_candidates = (
        HomepageEssential.query.options(selectinload(HomepageEssential.document))
        .filter_by(tenant_id=tenant.id, is_published=True)
        .order_by(HomepageEssential.display_order.asc(), HomepageEssential.created_at.asc())
        .limit(24)
        .all()
    )
    essentials = [
        item
        for item in essential_candidates
        if item.document and can_access_document(current_user, item.document)
    ][:8]

    out_rows = (
        db.session.query(LeaveRequest, Employee)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .filter(
            LeaveRequest.tenant_id == tenant.id,
            LeaveRequest.status == 'approved',
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today,
            Employee.deleted_at.is_(None),
        )
        .order_by(Employee.last_name.asc(), Employee.first_name.asc())
        .all()
    )
    people_out_by_employee = {}
    for leave_request, employee in out_rows:
        key = str(employee.id)
        expected_return = leave_request.end_date + timedelta(days=1)
        existing = people_out_by_employee.get(key)
        if existing and existing['expected_return_date'] >= expected_return.isoformat():
            continue
        people_out_by_employee[key] = {
            **_public_person(employee),
            'expected_return_date': expected_return.isoformat(),
            'availability_label': 'Out today',
        }
    people_out = list(people_out_by_employee.values())

    window_start = today - timedelta(days=settings.new_hire_window_days)
    new_hires = [
        {
            **_public_person(employee),
            'hire_date': employee.hire_date.isoformat(),
            'days_since_joining': (today - employee.hire_date).days,
        }
        for employee in employees
        if employee.hire_date and window_start <= employee.hire_date <= today
    ]
    new_hires.sort(key=lambda item: item['hire_date'], reverse=True)

    viewer = current_user.employee_profile
    if viewer and str(viewer.tenant_id) != str(tenant.id):
        viewer = None

    return success({
        'branding': {
            'organization_name': tenant.name,
            'banner_url': settings.banner_url,
            'logo_url': settings.logo_url,
            'welcome_message': settings.welcome_message,
        },
        'viewer': _self_profile(viewer) if viewer else {
            'full_name': current_user.full_name,
            'first_name': current_user.first_name,
            'job_title': current_user.role_names[0].replace('_', ' ').title() if current_user.role_names else None,
        },
        'assistant': {
            'enabled': settings.assistant_enabled,
            'url': settings.assistant_url,
        },
        'enabled_sections': settings.enabled_sections,
        'section_order': settings.section_order,
        'birthdays': _birthday_items(
            employees,
            today,
            settings.birthday_visibility_enabled,
        ),
        'essentials': [item.to_dict() for item in essentials],
        'people_out_today': people_out[:8],
        'events_this_week': [event.to_dict() for event in events],
        'new_hires': new_hires[:8],
        'anniversaries': _anniversary_items(
            employees,
            today,
            settings.anniversaries_enabled,
        ),
        'people_statistics': _people_statistics(
            employees,
            settings.people_statistics_enabled,
        ),
        'generated_at': now.isoformat(),
    })


@employee_home_bp.patch('/employee-home/profile')
@jwt_required()
def update_own_home_profile():
    employee = current_user.employee_profile
    if not employee:
        return fail(
            'EMPLOYEE_PROFILE_REQUIRED',
            'Your user account is not linked to an employee profile',
            409,
        )
    try:
        payload = EmployeeSelfProfileSchema().load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)

    if 'hobbies' in payload:
        employee.hobbies_json = sorted({item.strip() for item in payload.pop('hobbies') if item.strip()})
    for key, value in payload.items():
        setattr(employee, key, value)

    log_event(
        'employee.self_profile_update',
        'Employee',
        employee.id,
        tenant_id=employee.tenant_id,
        actor=current_user,
        metadata={'fields': sorted((request.get_json(silent=True) or {}).keys())},
    )
    db.session.commit()
    return success(_self_profile(employee), 'Your profile was updated')


@employee_home_bp.post('/employee-home/profile-image/<asset>')
@jwt_required()
def upload_own_profile_image(asset):
    employee = current_user.employee_profile
    if not employee:
        return fail(
            'EMPLOYEE_PROFILE_REQUIRED',
            'Your user account is not linked to an employee profile',
            409,
        )
    if asset not in {'photo', 'cover'}:
        return fail('INVALID_PROFILE_IMAGE', 'Unsupported profile image', 404)

    file = request.files.get('file')
    try:
        filename = save_employee_profile_image(
            file,
            employee.tenant_id,
            employee.id,
            asset,
        )
    except ValueError as exc:
        return fail('INVALID_PROFILE_IMAGE', str(exc), 422)

    field = 'profile_photo_url' if asset == 'photo' else 'profile_cover_url'
    previous_url = getattr(employee, field)
    previous_filename = _managed_profile_filename(previous_url, employee.id)
    image_url = url_for(
        'employee_home.employee_profile_image_asset',
        employee_id=employee.id,
        filename=filename,
    )
    setattr(employee, field, image_url)

    log_event(
        'employee.self_profile_image_update',
        'Employee',
        employee.id,
        tenant_id=employee.tenant_id,
        actor=current_user,
        metadata={'asset': asset},
    )
    db.session.commit()
    if previous_filename:
        delete_employee_profile_image(
            employee.tenant_id,
            employee.id,
            previous_filename,
        )
    return success(_self_profile(employee), 'Your profile image was updated')


@employee_home_bp.get(
    '/employee-home/profile-images/<employee_id>/<filename>',
)
@jwt_required()
def employee_profile_image_asset(employee_id, filename):
    tenant, error = _require_tenant()
    if error:
        return error
    employee = Employee.query.filter_by(
        id=employee_id,
        tenant_id=tenant.id,
        deleted_at=None,
    ).first()
    if not employee:
        return fail('PROFILE_IMAGE_NOT_FOUND', 'Profile image not found', 404)
    try:
        path = employee_profile_image_path(
            tenant.id,
            employee.id,
            filename,
        )
    except ValueError:
        return fail('PROFILE_IMAGE_NOT_FOUND', 'Profile image not found', 404)
    if not path.is_file():
        return fail('PROFILE_IMAGE_NOT_FOUND', 'Profile image not found', 404)
    return send_file(path, conditional=True)


@employee_home_bp.get('/employee-home/events/<event_id>')
@jwt_required()
def employee_home_event(event_id):
    tenant, error = _require_tenant()
    if error:
        return error
    event = OrganizationEvent.query.filter_by(
        id=event_id,
        tenant_id=tenant.id,
    ).first_or_404()
    is_home_admin = current_user.has_any_role(ADMIN_ROLES)
    if event.status != 'published' and not is_home_admin:
        return fail('EVENT_NOT_AVAILABLE', 'This event is not published', 404)
    if (
        event.audience == 'managers'
        and not current_user.has_role('MANAGER')
        and not is_home_admin
    ):
        return fail('EVENT_NOT_AVAILABLE', 'This event is not available', 404)
    return success(event.to_dict())


@employee_home_bp.get('/employee-home/branding/<tenant_id>/<filename>')
@jwt_required()
def homepage_branding_asset(tenant_id, filename):
    _, error = _require_tenant(tenant_id)
    if error:
        return error
    try:
        path = homepage_branding_path(tenant_id, filename)
    except ValueError:
        return fail('BRANDING_IMAGE_NOT_FOUND', 'Branding image not found', 404)
    if not path.is_file():
        return fail('BRANDING_IMAGE_NOT_FOUND', 'Branding image not found', 404)
    return send_file(path, conditional=True, max_age=3600)


@employee_home_bp.post(
    '/tenants/<tenant_id>/homepage-branding/<asset>',
)
@jwt_required()
def upload_homepage_branding(tenant_id, asset):
    _, error = _require_home_admin(tenant_id)
    if error:
        return error
    if asset not in {'banner', 'logo'}:
        return fail('VALIDATION_ERROR', 'Asset must be banner or logo', 422)
    file = request.files.get('file')
    try:
        filename = save_homepage_branding_image(file, tenant_id, asset)
    except ValueError as exc:
        return fail('VALIDATION_ERROR', str(exc), 422)

    settings = _settings_for(tenant_id, create=True)
    db.session.flush()
    field = f'{asset}_url'
    previous_url = getattr(settings, field)
    image_url = url_for(
        'employee_home.homepage_branding_asset',
        tenant_id=tenant_id,
        filename=filename,
    )
    setattr(settings, field, image_url)
    log_event(
        'employee_home.branding_upload',
        'TenantHomepageSettings',
        settings.id,
        tenant_id=tenant_id,
        actor=current_user,
        metadata={'asset': asset},
    )
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        delete_homepage_branding_image(tenant_id, filename)
        raise

    previous_filename = _managed_branding_filename(previous_url, tenant_id)
    if previous_filename and previous_filename != filename:
        delete_homepage_branding_image(tenant_id, previous_filename)
    return success(settings.to_dict(), f'{asset.title()} image uploaded')


@employee_home_bp.get('/tenants/<tenant_id>/homepage-settings')
@jwt_required()
def get_homepage_settings(tenant_id):
    _, error = _require_home_admin(tenant_id)
    if error:
        return error
    return success(_settings_for(tenant_id).to_dict())


@employee_home_bp.patch('/tenants/<tenant_id>/homepage-settings')
@jwt_required()
def update_homepage_settings(tenant_id):
    _, error = _require_home_admin(tenant_id)
    if error:
        return error
    try:
        payload = HomepageSettingsUpdateSchema().load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)

    settings = _settings_for(tenant_id, create=True)
    previous_branding = {
        field: getattr(settings, field)
        for field in ('banner_url', 'logo_url')
    }
    assistant_enabled = payload.get('assistant_enabled', settings.assistant_enabled)
    assistant_url = payload.get('assistant_url', settings.assistant_url)
    if assistant_enabled and not assistant_url:
        return fail(
            'VALIDATION_ERROR',
            {'assistant_url': ['An assistant URL is required when Ask Kinetic is enabled.']},
            422,
        )
    if 'section_order' in payload:
        ordered = list(dict.fromkeys(payload['section_order']))
        ordered.extend(section for section in DEFAULT_HOME_SECTIONS if section not in ordered)
        payload['section_order'] = ordered
    if 'enabled_sections' in payload:
        payload['enabled_sections'] = list(dict.fromkeys(payload['enabled_sections']))
    for key, value in payload.items():
        setattr(settings, key, value)

    log_event(
        'employee_home.settings_update',
        'TenantHomepageSettings',
        settings.id,
        tenant_id=tenant_id,
        actor=current_user,
        metadata={'fields': sorted(payload)},
    )
    db.session.commit()
    for field in ('banner_url', 'logo_url'):
        previous_url = previous_branding[field]
        if field not in payload or payload[field] == previous_url:
            continue
        previous_filename = _managed_branding_filename(previous_url, tenant_id)
        if previous_filename:
            delete_homepage_branding_image(tenant_id, previous_filename)
    return success(settings.to_dict(), 'Employee homepage settings updated')


@employee_home_bp.get('/tenants/<tenant_id>/events')
@jwt_required()
def list_homepage_events(tenant_id):
    _, error = _require_home_admin(tenant_id)
    if error:
        return error
    events = (
        OrganizationEvent.query.filter_by(tenant_id=tenant_id)
        .order_by(OrganizationEvent.starts_at.desc())
        .all()
    )
    return success({'items': [event.to_dict() for event in events]})


@employee_home_bp.post('/tenants/<tenant_id>/events')
@jwt_required()
def create_homepage_event(tenant_id):
    _, error = _require_home_admin(tenant_id)
    if error:
        return error
    try:
        payload = OrganizationEventCreateSchema().load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)

    event = OrganizationEvent(
        tenant_id=tenant_id,
        created_by_id=current_user.id,
        **payload,
    )
    if event.status == 'published':
        event.published_at = utcnow()
    db.session.add(event)
    db.session.flush()
    log_event(
        'employee_home.event_create',
        'OrganizationEvent',
        event.id,
        tenant_id=tenant_id,
        actor=current_user,
    )
    db.session.commit()
    return success(event.to_dict(), 'Organization event created', 201)


@employee_home_bp.patch('/tenants/<tenant_id>/events/<event_id>')
@jwt_required()
def update_homepage_event(tenant_id, event_id):
    _, error = _require_home_admin(tenant_id)
    if error:
        return error
    event = OrganizationEvent.query.filter_by(id=event_id, tenant_id=tenant_id).first_or_404()
    try:
        payload = OrganizationEventUpdateSchema().load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)

    starts_at = payload.get('starts_at', event.starts_at)
    ends_at = payload.get('ends_at', event.ends_at)
    if ends_at and ends_at < starts_at:
        return fail('VALIDATION_ERROR', {'ends_at': ['End time must be after the start time.']}, 422)

    was_published = event.status == 'published'
    for key, value in payload.items():
        setattr(event, key, value)
    if event.status == 'published' and not was_published:
        event.published_at = utcnow()

    log_event(
        'employee_home.event_update',
        'OrganizationEvent',
        event.id,
        tenant_id=tenant_id,
        actor=current_user,
        metadata={'fields': sorted(payload)},
    )
    db.session.commit()
    return success(event.to_dict(), 'Organization event updated')


@employee_home_bp.delete('/tenants/<tenant_id>/events/<event_id>')
@jwt_required()
def delete_homepage_event(tenant_id, event_id):
    _, error = _require_home_admin(tenant_id)
    if error:
        return error
    event = OrganizationEvent.query.filter_by(id=event_id, tenant_id=tenant_id).first_or_404()
    log_event(
        'employee_home.event_delete',
        'OrganizationEvent',
        event.id,
        tenant_id=tenant_id,
        actor=current_user,
    )
    db.session.delete(event)
    db.session.commit()
    return success({}, 'Organization event deleted')


@employee_home_bp.get('/tenants/<tenant_id>/homepage-document-options')
@jwt_required()
def homepage_document_options(tenant_id):
    _, error = _require_home_admin(tenant_id)
    if error:
        return error
    documents = (
        Document.query.filter_by(tenant_id=tenant_id, deleted_at=None)
        .order_by(Document.title.asc())
        .limit(250)
        .all()
    )
    return success({
        'items': [
            {
                'id': str(document.id),
                'title': document.title,
                'document_type': document.document_type,
            }
            for document in documents
        ],
    })


@employee_home_bp.get('/tenants/<tenant_id>/essentials')
@jwt_required()
def list_homepage_essentials(tenant_id):
    _, error = _require_home_admin(tenant_id)
    if error:
        return error
    items = (
        HomepageEssential.query.options(selectinload(HomepageEssential.document))
        .filter_by(tenant_id=tenant_id)
        .order_by(HomepageEssential.display_order.asc())
        .all()
    )
    return success({'items': [item.to_dict() for item in items]})


@employee_home_bp.post('/tenants/<tenant_id>/essentials')
@jwt_required()
def create_homepage_essential(tenant_id):
    _, error = _require_home_admin(tenant_id)
    if error:
        return error
    try:
        payload = HomepageEssentialCreateSchema().load(request.get_json(silent=True) or {})
        document = Document.query.filter_by(
            id=payload['document_id'],
            tenant_id=tenant_id,
            deleted_at=None,
        ).first()
        if not document:
            return fail('DOCUMENT_NOT_FOUND', 'Document not found for this organization', 404)
        item = HomepageEssential(tenant_id=tenant_id, **payload)
        db.session.add(item)
        db.session.flush()
        log_event(
            'employee_home.essential_create',
            'HomepageEssential',
            item.id,
            tenant_id=tenant_id,
            actor=current_user,
        )
        db.session.commit()
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except IntegrityError:
        db.session.rollback()
        return fail('ESSENTIAL_ALREADY_EXISTS', 'This document is already an employee essential', 409)
    return success(item.to_dict(), 'Employee essential added', 201)


@employee_home_bp.patch('/tenants/<tenant_id>/essentials/<essential_id>')
@jwt_required()
def update_homepage_essential(tenant_id, essential_id):
    _, error = _require_home_admin(tenant_id)
    if error:
        return error
    item = HomepageEssential.query.filter_by(id=essential_id, tenant_id=tenant_id).first_or_404()
    try:
        payload = HomepageEssentialUpdateSchema().load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    for key, value in payload.items():
        setattr(item, key, value)
    log_event(
        'employee_home.essential_update',
        'HomepageEssential',
        item.id,
        tenant_id=tenant_id,
        actor=current_user,
        metadata={'fields': sorted(payload)},
    )
    db.session.commit()
    return success(item.to_dict(), 'Employee essential updated')


@employee_home_bp.delete('/tenants/<tenant_id>/essentials/<essential_id>')
@jwt_required()
def delete_homepage_essential(tenant_id, essential_id):
    _, error = _require_home_admin(tenant_id)
    if error:
        return error
    item = HomepageEssential.query.filter_by(id=essential_id, tenant_id=tenant_id).first_or_404()
    log_event(
        'employee_home.essential_delete',
        'HomepageEssential',
        item.id,
        tenant_id=tenant_id,
        actor=current_user,
    )
    db.session.delete(item)
    db.session.commit()
    return success({}, 'Employee essential removed')
