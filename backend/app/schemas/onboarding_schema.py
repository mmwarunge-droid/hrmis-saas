from marshmallow import Schema, fields, validate


class OnboardingTaskCreateSchema(Schema):
    title = fields.Str(required=True)
    description = fields.Str(required=False, allow_none=True)
    assignee_role = fields.Str(required=False, validate=validate.OneOf(['EMPLOYEE','MANAGER','CLIENT_ADMIN','HR_CONSULTANT']))
    due_days_after_start = fields.Int(required=False)
    required = fields.Bool(required=False)


class OnboardingTemplateCreateSchema(Schema):
    name = fields.Str(required=True)
    description = fields.Str(required=False, allow_none=True)
    tasks = fields.List(fields.Nested(OnboardingTaskCreateSchema), required=False)


class OnboardingAssignSchema(Schema):
    employee_id = fields.UUID(required=True)
    template_id = fields.UUID(required=True)


class OnboardingTaskCompleteSchema(Schema):
    completion_notes = fields.Str(required=False, allow_none=True)
