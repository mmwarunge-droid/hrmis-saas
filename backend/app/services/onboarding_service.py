import math
from datetime import timedelta

from flask_jwt_extended import current_user
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Employee,
    EmployeeOnboardingTask,
    OnboardingResource,
    OnboardingTask,
    OnboardingTemplate,
    Role,
    Tenant,
    User,
    UserRole,
)
from app.models.base import utcnow
from app.services.audit_service import log_event
from app.services.notification_service import create_notification
from app.utils.file_storage import (
    detect_mp4_duration,
    save_onboarding_resource_file,
)


VIDEO_HEARTBEAT_MAX_GAP_SECONDS = 12.0
VIDEO_POSITION_DRIFT_SECONDS = 2.5
VIDEO_COMPLETION_TOLERANCE_SECONDS = 2.0
VIDEO_MIN_COMPLETION_TOLERANCE_SECONDS = 0.25
VIDEO_MAX_DURATION_SECONDS = 8 * 60 * 60


def _validated_video_duration(value):
    try:
        duration = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            'Training video duration could not be verified'
        ) from None

    if (
        not math.isfinite(duration)
        or duration <= 0
        or duration > VIDEO_MAX_DURATION_SECONDS
    ):
        raise ValueError(
            'Training video duration is outside the supported range'
        )
    return duration


def _video_completion_tolerance(duration):
    return min(
        VIDEO_COMPLETION_TOLERANCE_SECONDS,
        max(
            VIDEO_MIN_COMPLETION_TOLERANCE_SECONDS,
            duration * 0.005,
        ),
    )


def _ensure_video_duration(resource):
    duration = float(resource.duration_seconds or 0.0)
    if duration <= 0 and resource.original_filename.lower().endswith('.mp4'):
        detected = detect_mp4_duration(resource.file_path)
        if detected:
            duration = _validated_video_duration(detected)
            resource.duration_seconds = duration

    if duration <= 0:
        raise ValueError(
            'This training video does not have a verified duration. '
            'Upload it again before assigning it.'
        )
    return duration


def _video_progress_state(assignment):
    resource = assignment.task.resource
    duration = float(resource.duration_seconds or 0.0) if resource else 0.0
    verified = min(
        float(assignment.video_verified_seconds or 0.0),
        duration,
    )
    remaining = max(duration - verified, 0.0)
    ready = bool(
        duration > 0
        and remaining <= _video_completion_tolerance(duration)
    )
    return {
        'duration_seconds': duration,
        'verified_seconds': verified,
        'remaining_seconds': remaining,
        'verified_percent': (
            round((verified / duration) * 100, 1)
            if duration > 0
            else 0.0
        ),
        'resume_position_seconds': min(verified, duration),
        'completion_ready': ready,
        'completed_at': (
            assignment.video_completed_at.isoformat()
            if assignment.video_completed_at
            else None
        ),
    }


def video_progress_state(assignment):
    if assignment.task.task_type != 'video':
        return None
    return _video_progress_state(assignment)


def _video_completion_ready(assignment):
    if assignment.task.task_type != 'video':
        return True
    return _video_progress_state(assignment)['completion_ready']


def _assignable_user(employee, role_name):
    if role_name == 'EMPLOYEE':
        return employee.user
    if role_name == 'MANAGER':
        return employee.manager.user if employee.manager else None
    return User.query.filter(
        User.tenant_id == employee.tenant_id,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
        User.role_links.any(
            UserRole.role.has(Role.name == role_name),
        ),
    ).order_by(User.first_name.asc(), User.last_name.asc()).first()


def create_resource(
    file,
    tenant_id,
    uploader_id,
    *,
    duration_seconds=None,
):
    stored = save_onboarding_resource_file(file, tenant_id)
    detected_duration = stored.pop('detected_duration_seconds', None)
    verified_duration = None

    if stored['resource_type'] == 'video':
        if detected_duration:
            verified_duration = _validated_video_duration(
                detected_duration,
            )
        else:
            verified_duration = _validated_video_duration(
                duration_seconds,
            )

    resource = OnboardingResource(
        tenant_id=tenant_id,
        uploaded_by_id=uploader_id,
        duration_seconds=verified_duration,
        **stored,
    )
    db.session.add(resource)
    db.session.flush()
    log_event(
        'onboarding.resource_upload',
        'OnboardingResource',
        resource.id,
        tenant_id=tenant_id,
        metadata={
            'resource_type': resource.resource_type,
            'filename': resource.original_filename,
            'duration_seconds': resource.duration_seconds,
            'duration_source': (
                'server_mp4'
                if detected_duration
                else 'privileged_upload_metadata'
            ),
        },
    )
    db.session.commit()
    return resource


def _validated_task_payload(task_payload, tenant_id):
    task = dict(task_payload)
    task_type = task.get('task_type') or 'action'
    resource_id = task.get('resource_id')

    if task_type == 'action':
        if resource_id:
            raise ValueError('Action tasks cannot have a training resource')
        task['resource_id'] = None
        task.setdefault('requires_acknowledgement', False)
        return task

    if not resource_id:
        raise ValueError(
            f'{task_type.title()} tasks require an uploaded training resource'
        )

    resource = OnboardingResource.query.filter_by(
        id=resource_id,
        tenant_id=tenant_id,
    ).first()
    if not resource:
        raise ValueError('Training resource is invalid for this organization')
    if resource.resource_type != task_type:
        raise ValueError(
            f'Uploaded resource is {resource.resource_type}, not {task_type}'
        )
    if task_type == 'video':
        _ensure_video_duration(resource)

    task['requires_acknowledgement'] = task.get(
        'requires_acknowledgement',
        True,
    )
    return task


def create_template(payload, tenant_id):
    payload = dict(payload)
    tasks = payload.pop('tasks', [])
    validated_tasks = [
        _validated_task_payload(task, tenant_id)
        for task in tasks
    ]

    template = OnboardingTemplate(tenant_id=tenant_id, **payload)
    db.session.add(template)
    db.session.flush()
    for task in validated_tasks:
        db.session.add(
            OnboardingTask(
                tenant_id=tenant_id,
                template_id=template.id,
                **task,
            )
        )
    log_event(
        'onboarding.template_create',
        'OnboardingTemplate',
        template.id,
        tenant_id=tenant_id,
    )
    db.session.commit()
    return template


def update_template(template, payload):
    payload = dict(payload)
    tasks = payload.pop('tasks', None)
    for field in ('name', 'description', 'is_active'):
        if field in payload:
            setattr(template, field, payload[field])
    if tasks is not None:
        if template.tasks and any(task.assignments for task in template.tasks):
            raise ValueError(
                'Templates with assigned tasks cannot replace their task list. '
                'Archive the template and create a new version instead.'
            )
        validated_tasks = [
            _validated_task_payload(task, template.tenant_id)
            for task in tasks
        ]
        template.tasks.clear()
        db.session.flush()
        for task in validated_tasks:
            template.tasks.append(
                OnboardingTask(
                    tenant_id=template.tenant_id,
                    **task,
                )
            )
    log_event(
        'onboarding.template_update',
        'OnboardingTemplate',
        template.id,
        tenant_id=template.tenant_id,
    )
    db.session.commit()
    return template


def assign_template(employee_id, template_id, tenant_id):
    employee = Employee.query.filter_by(
        id=employee_id,
        tenant_id=tenant_id,
        deleted_at=None,
    ).first()
    template = OnboardingTemplate.query.filter_by(
        id=template_id,
        tenant_id=tenant_id,
        is_active=True,
    ).first()
    if not employee or not template:
        raise ValueError('Invalid employee_id or template_id for this tenant')

    tenant = db.session.get(Tenant, tenant_id)
    organization_name = (
        tenant.name
        if tenant and tenant.name
        else 'Your organization'
    )

    created = []
    for task in template.tasks:
        existing = EmployeeOnboardingTask.query.filter_by(
            tenant_id=tenant_id,
            employee_id=employee.id,
            task_id=task.id,
        ).first()
        if existing:
            created.append(existing)
            continue
        assignee = _assignable_user(employee, task.assignee_role)
        due_date = employee.hire_date + timedelta(
            days=task.due_days_after_start or 0,
        )
        status = 'overdue' if due_date < utcnow().date() else 'pending'
        assignment = EmployeeOnboardingTask(
            tenant_id=tenant_id,
            employee_id=employee.id,
            task_id=task.id,
            assigned_to_user_id=assignee.id if assignee else None,
            due_date=due_date,
            status=status,
        )
        db.session.add(assignment)
        db.session.flush()
        created.append(assignment)
        if assignee:
            create_notification(
                tenant_id=tenant_id,
                user_id=assignee.id,
                title=(
                    f'{organization_name} assigned you a Kinetic task'
                ),
                body=(
                    f'{task.title} · due {due_date.isoformat()}'
                ),
                notification_type='onboarding',
                action_url='/tasks',
                priority='high' if status == 'overdue' else 'normal',
                metadata={
                    'assignment_id': str(assignment.id),
                    'employee_id': str(employee.id),
                    'task_id': str(task.id),
                    'template_id': str(template.id),
                    'task_type': task.task_type,
                },
            )
    log_event(
        'onboarding.assign',
        'Employee',
        employee.id,
        tenant_id=tenant_id,
        metadata={'template_id': str(template.id)},
    )
    db.session.commit()
    return created


def update_assignment(assignment, payload, actor):
    if 'assigned_to_user_id' in payload:
        assignee_id = payload['assigned_to_user_id']
        if assignee_id:
            assignee = User.query.filter_by(
                id=assignee_id,
                tenant_id=assignment.tenant_id,
                is_active=True,
                deleted_at=None,
            ).first()
            if not assignee:
                raise ValueError('Assignee is invalid for this organization')
        assignment.assigned_to_user_id = assignee_id

    if 'status' in payload:
        next_status = payload['status']
        if (
            next_status == 'completed'
            and assignment.task.task_type == 'video'
        ):
            raise ValueError(
                'Video training must be completed and acknowledged by the '
                'assigned user. Use waived for an administrative override.'
            )

        assignment.status = next_status
        if assignment.status == 'completed':
            assignment.completed_at = utcnow()
        elif assignment.status not in {'completed', 'waived'}:
            assignment.completed_at = None
    if 'completion_notes' in payload:
        assignment.completion_notes = payload['completion_notes']

    log_event(
        'onboarding.assignment_update',
        'EmployeeOnboardingTask',
        assignment.id,
        tenant_id=assignment.tenant_id,
        metadata={'status': assignment.status},
    )
    db.session.commit()
    return assignment


def mark_assignment_viewed(assignment):
    if assignment.task.resource_id and not assignment.resource_viewed_at:
        assignment.resource_viewed_at = utcnow()
    if assignment.status == 'pending':
        assignment.status = 'in_progress'
    log_event(
        'onboarding.resource_view',
        'EmployeeOnboardingTask',
        assignment.id,
        tenant_id=assignment.tenant_id,
        metadata={'resource_id': str(assignment.task.resource_id)},
    )
    db.session.commit()
    return assignment


def record_video_progress(assignment, *, event, position_seconds):
    if assignment.task.task_type != 'video':
        raise ValueError('This onboarding task is not a video training task')
    if not assignment.task.resource:
        raise ValueError('This video training task has no training resource')

    resource = assignment.task.resource
    duration = _ensure_video_duration(resource)

    now = utcnow()
    position = max(0.0, min(float(position_seconds), duration))
    verified = min(
        float(assignment.video_verified_seconds or 0.0),
        duration,
    )
    seek_blocked = False

    if not assignment.video_started_at:
        assignment.video_started_at = now
    if not assignment.resource_viewed_at:
        assignment.resource_viewed_at = now
    if assignment.status == 'pending':
        assignment.status = 'in_progress'

    if event == 'start':
        if position > verified:
            position = verified
            seek_blocked = True
        assignment.video_last_position_seconds = position
        assignment.video_last_heartbeat_at = now
    else:
        last_at = assignment.video_last_heartbeat_at
        last_position = float(assignment.video_last_position_seconds or 0.0)

        if last_at is None:
            if position > verified:
                position = verified
                seek_blocked = True
        else:
            elapsed = max((now - last_at).total_seconds(), 0.0)
            position_delta = position - last_position
            max_forward_position = (
                verified
                + VIDEO_HEARTBEAT_MAX_GAP_SECONDS
                + VIDEO_POSITION_DRIFT_SECONDS
            )

            invalid_gap = elapsed > VIDEO_HEARTBEAT_MAX_GAP_SECONDS
            invalid_forward_seek = (
                position_delta > elapsed + VIDEO_POSITION_DRIFT_SECONDS
                or position > max_forward_position
            )

            if invalid_gap or invalid_forward_seek:
                if position > verified:
                    position = verified
                    seek_blocked = True
            elif position_delta >= 0:
                new_segment_start = max(last_position, verified)
                candidate = max(position - new_segment_start, 0.0)
                credited = min(
                    candidate,
                    elapsed,
                    VIDEO_HEARTBEAT_MAX_GAP_SECONDS,
                )
                verified = min(duration, verified + credited)
                assignment.video_verified_seconds = verified

        assignment.video_last_position_seconds = position
        assignment.video_last_heartbeat_at = (
            now if event == 'heartbeat' else None
        )

    progress = _video_progress_state(assignment)
    newly_completed = (
        progress['completion_ready']
        and not assignment.video_completed_at
    )
    if newly_completed:
        assignment.video_completed_at = now
        log_event(
            'onboarding.video_watch_complete',
            'EmployeeOnboardingTask',
            assignment.id,
            tenant_id=assignment.tenant_id,
            metadata={
                'duration_seconds': progress['duration_seconds'],
                'verified_seconds': progress['verified_seconds'],
            },
        )

    db.session.commit()
    progress = _video_progress_state(assignment)
    progress['seek_blocked'] = seek_blocked
    return assignment, progress


def complete_assignment(assignment, notes=None, acknowledged=False):
    if (
        assignment.task.task_type == 'video'
        and not _video_completion_ready(assignment)
    ):
        raise ValueError(
            'Watch the full training video before completing this task'
        )

    if assignment.task.requires_acknowledgement and not acknowledged:
        raise ValueError(
            'You must acknowledge this training requirement before completing it'
        )

    now = utcnow()
    assignment.status = 'completed'
    assignment.completed_at = now
    assignment.completion_notes = notes

    if assignment.task.resource_id and not assignment.resource_viewed_at:
        assignment.resource_viewed_at = now
    if acknowledged:
        assignment.acknowledged_at = now

    log_event(
        'onboarding.task_complete',
        'EmployeeOnboardingTask',
        assignment.id,
        tenant_id=assignment.tenant_id,
        metadata={
            'acknowledged': bool(assignment.acknowledged_at),
            'task_type': assignment.task.task_type,
        },
    )
    db.session.commit()
    return assignment


def can_access_resource(resource):
    if current_user.has_permissions({'onboarding:create'}):
        return True
    if current_user.has_permissions({'onboarding:assign'}):
        return True

    query = EmployeeOnboardingTask.query.join(
        EmployeeOnboardingTask.task,
    ).filter(
        EmployeeOnboardingTask.tenant_id == resource.tenant_id,
        OnboardingTask.resource_id == resource.id,
    )

    access_clauses = [
        EmployeeOnboardingTask.assigned_to_user_id == current_user.id,
    ]
    if current_user.employee_profile:
        access_clauses.append(
            EmployeeOnboardingTask.employee_id
            == current_user.employee_profile.id
        )

    return query.filter(or_(*access_clauses)).first() is not None
