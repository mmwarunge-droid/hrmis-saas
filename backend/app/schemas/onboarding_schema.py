from marshmallow import Schema, fields, validate


class OnboardingTaskCreateSchema(Schema):
    title = fields.Str(required=True)
    description = fields.Str(required=False, allow_none=True)
    task_type = fields.Str(
        required=False,
        validate=validate.OneOf(['action', 'document', 'video']),
    )
    resource_id = fields.UUID(required=False, allow_none=True)
    assignee_role = fields.Str(
        required=False,
        validate=validate.OneOf(
            ['EMPLOYEE', 'MANAGER', 'CLIENT_ADMIN', 'HR_CONSULTANT']
        ),
    )
    due_days_after_start = fields.Int(required=False, validate=validate.Range(min=0))
    required = fields.Bool(required=False)
    requires_acknowledgement = fields.Bool(required=False)


class OnboardingTemplateCreateSchema(Schema):
    name = fields.Str(required=True)
    description = fields.Str(required=False, allow_none=True)
    tasks = fields.List(fields.Nested(OnboardingTaskCreateSchema), required=False)


class OnboardingAssignSchema(Schema):
    employee_id = fields.UUID(required=True)
    template_id = fields.UUID(required=True)


class OnboardingTaskCompleteSchema(Schema):
    completion_notes = fields.Str(required=False, allow_none=True)
    acknowledged = fields.Bool(required=False)


class OnboardingTemplateUpdateSchema(Schema):
    name = fields.Str(required=False)
    description = fields.Str(required=False, allow_none=True)
    is_active = fields.Bool(required=False)
    tasks = fields.List(
        fields.Nested(OnboardingTaskCreateSchema),
        required=False,
    )


class OnboardingAssignmentUpdateSchema(Schema):
    status = fields.Str(
        required=False,
        validate=validate.OneOf(
            ['pending', 'in_progress', 'completed', 'waived', 'overdue']
        ),
    )
    assigned_to_user_id = fields.UUID(required=False, allow_none=True)
    completion_notes = fields.Str(required=False, allow_none=True)
