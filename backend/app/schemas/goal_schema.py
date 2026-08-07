from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class GoalCreateSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=2, max=200))
    description = fields.Str(required=False, allow_none=True)
    owner_type = fields.Str(
        required=True,
        validate=validate.OneOf(['organization', 'department', 'employee']),
    )
    employee_id = fields.UUID(required=False, allow_none=True)
    department_id = fields.UUID(required=False, allow_none=True)
    target_value = fields.Decimal(required=True, as_string=False, places=2)
    current_value = fields.Decimal(required=False, as_string=False, places=2)
    unit = fields.Str(required=True, validate=validate.Length(min=1, max=40))
    start_date = fields.Date(required=True)
    due_date = fields.Date(required=True)
    weight = fields.Decimal(required=False, as_string=False, places=2)
    status = fields.Str(
        required=False,
        validate=validate.OneOf(['draft', 'active']),
    )

    @validates_schema
    def validate_owner_and_dates(self, data, **kwargs):
        owner_type = data.get('owner_type')
        if owner_type == 'employee' and not data.get('employee_id'):
            raise ValidationError(
                {'employee_id': ['Employee goals require an employee.']}
            )
        if owner_type == 'department' and not data.get('department_id'):
            raise ValidationError(
                {'department_id': ['Department goals require a department.']}
            )
        if data.get('due_date') and data.get('start_date'):
            if data['due_date'] < data['start_date']:
                raise ValidationError(
                    {'due_date': ['Due date must be on or after start date.']}
                )


class GoalUpdateSchema(Schema):
    title = fields.Str(required=False, validate=validate.Length(min=2, max=200))
    description = fields.Str(required=False, allow_none=True)
    target_value = fields.Decimal(required=False, as_string=False, places=2)
    unit = fields.Str(required=False, validate=validate.Length(min=1, max=40))
    start_date = fields.Date(required=False)
    due_date = fields.Date(required=False)
    weight = fields.Decimal(required=False, as_string=False, places=2)
    status = fields.Str(
        required=False,
        validate=validate.OneOf(['draft', 'active', 'completed', 'cancelled']),
    )
    health = fields.Str(
        required=False,
        validate=validate.OneOf(['on_track', 'at_risk', 'off_track', 'completed']),
    )


class GoalCheckInSchema(Schema):
    current_value = fields.Decimal(required=True, as_string=False, places=2)
    health = fields.Str(
        required=False,
        validate=validate.OneOf(['on_track', 'at_risk', 'off_track']),
    )
    note = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))
