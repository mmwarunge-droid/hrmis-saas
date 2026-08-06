from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import false, or_

from app.extensions import db
from app.models import Department, Employee, Goal, GoalCheckIn
from app.models.base import utcnow
from app.services.audit_service import log_event
from app.services.notification_service import create_notification
from app.utils.decorators import tenant_query

ADMIN_ROLES = {
    'SUPER_ADMIN',
    'ORGANIZATION_OWNER',
    'HR_CONSULTANT',
    'CLIENT_ADMIN',
}


def progress_percent(current_value, target_value):
    current = Decimal(str(current_value or 0))
    target = Decimal(str(target_value or 0))
    if target <= 0:
        raise ValueError('Goal target must be greater than zero')
    return max(Decimal('0'), min(Decimal('100'), (current / target) * 100))


def inferred_health(goal, *, today=None):
    today = today or date.today()
    progress = Decimal(str(goal.progress_percent or 0))
    if goal.status == 'completed' or progress >= 100:
        return 'completed'
    if goal.due_date < today:
        return 'off_track'
    days_remaining = (goal.due_date - today).days
    duration = max((goal.due_date - goal.start_date).days, 1)
    elapsed = max((today - goal.start_date).days, 0)
    expected = min(Decimal('100'), Decimal(elapsed * 100) / Decimal(duration))
    if days_remaining <= 14 and progress < Decimal('70'):
        return 'at_risk'
    if progress + Decimal('15') < expected:
        return 'at_risk'
    return 'on_track'


def _direct_report_ids(user):
    if not user.employee_profile:
        return []
    return [
        row[0]
        for row in Employee.query.with_entities(Employee.id).filter(
            Employee.tenant_id == user.tenant_id,
            Employee.manager_id == user.employee_profile.id,
            Employee.deleted_at.is_(None),
        ).all()
    ]


def goal_scope_query(user, query=None):
    if query is None:
        query = tenant_query(Goal)
    if user.has_any_role(ADMIN_ROLES):
        return query

    employee = user.employee_profile
    if not employee:
        return query.filter(Goal.owner_type == 'organization')

    clauses = [Goal.owner_type == 'organization']
    if employee.department_id:
        clauses.append(
            db.and_(
                Goal.owner_type == 'department',
                Goal.department_id == employee.department_id,
            )
        )
    employee_ids = [employee.id]
    if user.has_role('MANAGER'):
        employee_ids.extend(_direct_report_ids(user))
    clauses.append(
        db.and_(
            Goal.owner_type == 'employee',
            Goal.employee_id.in_(employee_ids),
        )
    )
    return query.filter(or_(*clauses))


def _validate_owner(payload, tenant_id):
    owner_type = payload['owner_type']
    employee = None
    department = None
    if owner_type == 'employee':
        employee = Employee.query.filter_by(
            id=payload.get('employee_id'),
            tenant_id=tenant_id,
            deleted_at=None,
        ).first()
        if not employee:
            raise ValueError('Employee goal owner is invalid for this organization')
        payload['department_id'] = None
    elif owner_type == 'department':
        department = Department.query.filter_by(
            id=payload.get('department_id'),
            tenant_id=tenant_id,
            deleted_at=None,
        ).first()
        if not department:
            raise ValueError('Department goal owner is invalid for this organization')
        payload['employee_id'] = None
    else:
        payload['employee_id'] = None
        payload['department_id'] = None
    return employee, department


def can_manage_goal(actor, goal=None, payload=None):
    if actor.has_any_role(ADMIN_ROLES):
        return True
    if not actor.has_role('MANAGER') or not actor.employee_profile:
        return False

    employee_profile = actor.employee_profile
    if goal:
        if goal.owner_type == 'employee':
            return (
                str(goal.employee_id) == str(employee_profile.id)
                or str(goal.employee.manager_id) == str(employee_profile.id)
            )
        if goal.owner_type == 'department':
            return str(goal.department_id) == str(employee_profile.department_id)
        return False

    owner_type = payload.get('owner_type') if payload else None
    if owner_type == 'employee':
        employee = Employee.query.filter_by(
            id=payload.get('employee_id'),
            tenant_id=actor.tenant_id,
            deleted_at=None,
        ).first()
        return bool(
            employee
            and (
                str(employee.id) == str(employee_profile.id)
                or str(employee.manager_id) == str(employee_profile.id)
            )
        )
    if owner_type == 'department':
        return str(payload.get('department_id')) == str(employee_profile.department_id)
    return False


def create_goal(payload, tenant_id, actor):
    if not can_manage_goal(actor, payload=payload):
        raise PermissionError('You cannot create a goal for this owner')
    employee, _department = _validate_owner(payload, tenant_id)
    current_value = payload.get('current_value', Decimal('0'))
    target_value = payload['target_value']
    progress = progress_percent(current_value, target_value)
    goal = Goal(
        tenant_id=tenant_id,
        created_by_user_id=actor.id,
        progress_percent=progress,
        current_value=current_value,
        **{key: value for key, value in payload.items() if key != 'current_value'},
    )
    goal.health = inferred_health(goal)
    if progress >= 100:
        goal.status = 'completed'
        goal.health = 'completed'
    db.session.add(goal)
    db.session.flush()

    if employee and employee.user_id and str(employee.user_id) != str(actor.id):
        create_notification(
            tenant_id=tenant_id,
            user_id=employee.user_id,
            title='A new goal was assigned to you',
            body=f'{goal.title} · due {goal.due_date.isoformat()}',
            notification_type='goal',
            action_url='/goals',
            priority='normal',
            metadata={'goal_id': str(goal.id)},
        )
    log_event(
        'goal.create',
        'Goal',
        goal.id,
        tenant_id=tenant_id,
        metadata={
            'owner_type': goal.owner_type,
            'employee_id': str(goal.employee_id) if goal.employee_id else None,
            'department_id': str(goal.department_id) if goal.department_id else None,
        },
    )
    db.session.commit()
    return goal


def update_goal(goal, payload, actor):
    if not can_manage_goal(actor, goal=goal):
        raise PermissionError('You cannot update this goal')
    for field, value in payload.items():
        setattr(goal, field, value)
    if goal.due_date < goal.start_date:
        raise ValueError('Due date must be on or after start date')
    goal.progress_percent = progress_percent(
        goal.current_value,
        goal.target_value,
    )
    if goal.status == 'completed' or goal.progress_percent >= 100:
        goal.status = 'completed'
        goal.health = 'completed'
    elif 'health' not in payload:
        goal.health = inferred_health(goal)
    log_event(
        'goal.update',
        'Goal',
        goal.id,
        tenant_id=goal.tenant_id,
        metadata={'status': goal.status, 'health': goal.health},
    )
    db.session.commit()
    return goal


def can_check_in(actor, goal):
    if actor.has_any_role(ADMIN_ROLES):
        return True
    if actor.has_role('MANAGER'):
        return can_manage_goal(actor, goal=goal)
    return bool(
        actor.employee_profile
        and goal.owner_type == 'employee'
        and str(goal.employee_id) == str(actor.employee_profile.id)
    )


def add_check_in(goal, payload, actor):
    if goal.status in {'completed', 'cancelled'}:
        raise ValueError('Completed or cancelled goals cannot receive check-ins')
    if not can_check_in(actor, goal):
        raise PermissionError('You cannot record progress for this goal')

    current_value = payload['current_value']
    progress = progress_percent(current_value, goal.target_value)
    goal.current_value = current_value
    goal.progress_percent = progress
    goal.last_check_in_at = utcnow()
    if progress >= 100:
        goal.status = 'completed'
        goal.health = 'completed'
    else:
        goal.health = payload.get('health') or inferred_health(goal)

    check_in = GoalCheckIn(
        tenant_id=goal.tenant_id,
        goal_id=goal.id,
        actor_user_id=actor.id,
        current_value=current_value,
        progress_percent=progress,
        health=goal.health,
        note=payload.get('note'),
    )
    db.session.add(check_in)
    db.session.flush()

    if goal.created_by_user_id and str(goal.created_by_user_id) != str(actor.id):
        create_notification(
            tenant_id=goal.tenant_id,
            user_id=goal.created_by_user_id,
            title=f'Goal progress updated: {goal.title}',
            body=f'Progress is now {float(progress):.0f}%.',
            notification_type='goal',
            action_url='/goals',
            metadata={'goal_id': str(goal.id)},
        )
    log_event(
        'goal.check_in',
        'Goal',
        goal.id,
        tenant_id=goal.tenant_id,
        metadata={
            'progress_percent': float(progress),
            'health': goal.health,
        },
    )
    db.session.commit()
    return check_in


def goal_summary(user):
    query = goal_scope_query(user)
    active = query.filter(Goal.status.in_(['draft', 'active']))
    today = date.today()
    aggregate = active.with_entities(
        db.func.count(Goal.id),
        db.func.avg(Goal.progress_percent),
    ).first()
    return {
        'total': query.count(),
        'active': aggregate[0] or 0,
        'average_progress': round(float(aggregate[1] or 0), 1),
        'on_track': active.filter(Goal.health == 'on_track').count(),
        'at_risk': active.filter(Goal.health == 'at_risk').count(),
        'off_track': active.filter(Goal.health == 'off_track').count(),
        'overdue': active.filter(
            Goal.due_date < today,
            Goal.progress_percent < 100,
        ).count(),
        'completed': query.filter(Goal.status == 'completed').count(),
        'due_soon': active.filter(
            Goal.due_date >= today,
            Goal.due_date <= today + timedelta(days=14),
        ).count(),
    }
