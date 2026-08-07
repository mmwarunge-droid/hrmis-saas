from marshmallow import Schema, fields, validate


class TenantCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=2, max=160))
    slug = fields.Str(required=True, validate=validate.Regexp(r'^[a-z0-9-]+$'))
    legal_name = fields.Str(required=False, allow_none=True)
    country = fields.Str(required=False, allow_none=True)
    industry = fields.Str(required=False, allow_none=True)
    compliance_region = fields.Str(required=False, allow_none=True)


class TenantUpdateSchema(Schema):
    name = fields.Str(required=False, validate=validate.Length(min=2, max=160))
    legal_name = fields.Str(required=False, allow_none=True)
    country = fields.Str(required=False, allow_none=True)
    industry = fields.Str(required=False, allow_none=True)
    compliance_region = fields.Str(required=False, allow_none=True)
    status = fields.Str(required=False, validate=validate.OneOf(['active', 'suspended', 'archived']))
    billing_plan = fields.Str(required=False)


class EmployeeAccountProfileSchema(Schema):
    employee_number = fields.Str(required=True, validate=validate.Length(min=1, max=80))
    hire_date = fields.Date(required=True)
    job_title = fields.Str(required=False, allow_none=True)
    department_id = fields.UUID(required=False, allow_none=True)
    manager_id = fields.UUID(required=False, allow_none=True)
    work_location = fields.Str(required=False, allow_none=True)
    employment_type = fields.Str(
        required=False,
        load_default='full_time',
        validate=validate.OneOf(['full_time', 'part_time', 'contractor', 'intern', 'temporary']),
    )


class UserCreateSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    email = fields.Email(required=True)
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    password = fields.Str(required=True, validate=validate.Length(min=10, max=128), load_only=True)
    roles = fields.List(fields.Str(), required=True, validate=validate.Length(min=1))
    employee_profile = fields.Nested(EmployeeAccountProfileSchema, required=False, allow_none=True)


class OrganizationAdminSchema(Schema):
    email = fields.Email(required=True)
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    password = fields.Str(required=True, validate=validate.Length(min=10, max=128), load_only=True)


class OrganizationProvisionSchema(Schema):
    organization = fields.Nested(TenantCreateSchema, required=True)
    admin = fields.Nested(OrganizationAdminSchema, required=True)


class UserUpdateSchema(Schema):
    first_name = fields.Str(required=False)
    last_name = fields.Str(required=False)
    is_active = fields.Bool(required=False)


class UserRoleUpdateSchema(Schema):
    roles = fields.List(fields.Str(), required=True, validate=validate.Length(min=1))

class TenantMfaPolicySchema(Schema):
    mode = fields.Str(
        required=False,
        validate=validate.OneOf([
            'optional',
            'privileged',
            'managers_and_privileged',
            'all_users',
        ]),
    )
    grace_days = fields.Int(
        required=False,
        validate=validate.Range(min=0, max=365),
    )
    enforcement_date = fields.Date(
        required=False,
        allow_none=True,
    )


class MfaAdminResetSchema(Schema):
    reason = fields.Str(
        required=True,
        validate=validate.Length(min=5, max=500),
    )
    password = fields.Str(
        required=True,
        load_only=True,
        validate=validate.Length(min=1, max=128),
    )
    code = fields.Str(
        required=True,
        validate=validate.Length(min=6, max=32),
    )


class UserEmployeeLinkSchema(Schema):
    employee_id = fields.UUID(required=False, allow_none=True)
