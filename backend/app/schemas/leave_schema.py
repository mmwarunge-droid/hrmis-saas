from marshmallow import Schema, fields, validate


class LeaveTypeCreateSchema(Schema):
    name = fields.Str(required=True)
    annual_entitlement_days = fields.Decimal(required=False, places=2, as_string=False)
    accrual_method = fields.Str(required=False, validate=validate.OneOf(['annual','monthly','manual','none']))
    requires_approval = fields.Bool(required=False)
    is_active = fields.Bool(required=False)
    carryover_allowed = fields.Bool(required=False)
    max_carryover_days = fields.Decimal(required=False, places=2, as_string=False)


class LeaveRequestCreateSchema(Schema):
    employee_id = fields.UUID(required=True)
    leave_type_id = fields.UUID(required=True)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    total_days = fields.Decimal(required=True, places=2, as_string=False)
    reason = fields.Str(required=False, allow_none=True)


class LeaveDecisionSchema(Schema):
    decision_notes = fields.Str(required=False, allow_none=True)
