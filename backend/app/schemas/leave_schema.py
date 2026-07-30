from marshmallow import Schema, fields, validate


ENTITLEMENT_MODES = [
    'accrued',
    'granted_upfront',
    'event_based',
    'unlimited',
    'manual',
]
ACCRUAL_METHODS = ['annual', 'monthly', 'manual', 'none']


class LeaveTypeCreateSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    code = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=80),
    )
    name = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=100),
    )
    annual_entitlement_days = fields.Decimal(
        required=False,
        places=2,
        as_string=False,
        validate=validate.Range(min=0),
    )
    accrual_method = fields.Str(
        required=False,
        validate=validate.OneOf(ACCRUAL_METHODS),
    )
    entitlement_mode = fields.Str(
        required=False,
        validate=validate.OneOf(ENTITLEMENT_MODES),
    )
    pay_percentage = fields.Decimal(
        required=False,
        places=2,
        as_string=False,
        validate=validate.Range(min=0, max=100),
    )
    eligibility_after_months = fields.Int(
        required=False,
        validate=validate.Range(min=0),
    )
    requires_approval = fields.Bool(required=False)
    is_active = fields.Bool(required=False)
    carryover_allowed = fields.Bool(required=False)
    max_carryover_days = fields.Decimal(
        required=False,
        places=2,
        as_string=False,
        validate=validate.Range(min=0),
    )
    allow_negative_balance = fields.Bool(required=False)
    minimum_notice_days = fields.Int(
        required=False,
        validate=validate.Range(min=0),
    )
    documentation_after_days = fields.Int(
        required=False,
        allow_none=True,
        validate=validate.Range(min=0),
    )


class LeavePolicyOverrideSchema(Schema):
    code = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=80),
    )
    name = fields.Str(
        required=False,
        validate=validate.Length(min=2, max=100),
    )
    annual_entitlement_days = fields.Decimal(
        required=False,
        places=2,
        as_string=False,
        validate=validate.Range(min=0),
    )
    accrual_method = fields.Str(
        required=False,
        validate=validate.OneOf(ACCRUAL_METHODS),
    )
    entitlement_mode = fields.Str(
        required=False,
        validate=validate.OneOf(ENTITLEMENT_MODES),
    )
    pay_percentage = fields.Decimal(
        required=False,
        places=2,
        as_string=False,
        validate=validate.Range(min=0, max=100),
    )
    eligibility_after_months = fields.Int(
        required=False,
        validate=validate.Range(min=0),
    )
    requires_approval = fields.Bool(required=False)
    carryover_allowed = fields.Bool(required=False)
    max_carryover_days = fields.Decimal(
        required=False,
        places=2,
        as_string=False,
        validate=validate.Range(min=0),
    )
    allow_negative_balance = fields.Bool(required=False)
    minimum_notice_days = fields.Int(
        required=False,
        validate=validate.Range(min=0),
    )
    documentation_after_days = fields.Int(
        required=False,
        allow_none=True,
        validate=validate.Range(min=0),
    )


class LeavePolicyPackApplySchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    policies = fields.List(
        fields.Nested(LeavePolicyOverrideSchema),
        required=False,
        load_default=list,
    )
    initialize_balances = fields.Bool(
        required=False,
        load_default=True,
    )
    as_of_date = fields.Date(required=False, allow_none=True)


class LeaveGovernanceSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    organization_owner_user_id = fields.UUID(required=True)
    alternate_approver_user_id = fields.UUID(required=True)


class LeaveBalanceInitializeSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    year = fields.Int(
        required=False,
        validate=validate.Range(min=2000, max=2200),
    )
    as_of_date = fields.Date(required=False, allow_none=True)
    overwrite_unused = fields.Bool(
        required=False,
        load_default=False,
    )


class LeaveRequestCreateSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    employee_id = fields.UUID(required=False, allow_none=True)
    leave_type_id = fields.UUID(required=True)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    total_days = fields.Decimal(
        required=False,
        places=2,
        as_string=False,
    )
    reason = fields.Str(required=False, allow_none=True)


class LeaveDecisionSchema(Schema):
    decision_notes = fields.Str(required=False, allow_none=True)
