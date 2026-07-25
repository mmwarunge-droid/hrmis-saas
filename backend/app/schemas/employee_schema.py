from datetime import date

from marshmallow import Schema, fields, validate


class DepartmentSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    name = fields.Str(required=True, validate=validate.Length(min=2, max=140))
    code = fields.Str(required=False, allow_none=True, validate=validate.Length(max=40))
    parent_department_id = fields.UUID(required=False, allow_none=True)
    head_employee_id = fields.UUID(required=False, allow_none=True)


class DepartmentUpdateSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    name = fields.Str(required=False, validate=validate.Length(min=2, max=140))
    code = fields.Str(required=False, allow_none=True, validate=validate.Length(max=40))
    parent_department_id = fields.UUID(required=False, allow_none=True)
    head_employee_id = fields.UUID(required=False, allow_none=True)


class DepartmentArchiveSchema(Schema):
    replacement_department_id = fields.UUID(required=False, allow_none=True)
    effective_date = fields.Date(required=False, load_default=date.today)
    reason = fields.Str(
        required=False,
        load_default='Department archived',
        validate=validate.Length(min=3, max=255),
    )


class BulkDepartmentTransferSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    employee_ids = fields.List(
        fields.UUID(),
        required=True,
        validate=validate.Length(min=1, max=500),
    )
    department_id = fields.UUID(required=True, allow_none=True)
    effective_date = fields.Date(required=False, load_default=date.today)
    reason = fields.Str(required=True, validate=validate.Length(min=3, max=255))


class EmployeeAccessProvisionSchema(Schema):
    password = fields.Str(required=True, validate=validate.Length(min=10, max=128), load_only=True)
    roles = fields.List(
        fields.Str(validate=validate.OneOf(['EMPLOYEE', 'MANAGER'])),
        required=True,
        validate=validate.Length(equal=1),
    )


class EmployeeCreateSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    user_id = fields.UUID(required=False, allow_none=True)
    employee_number = fields.Str(required=True, validate=validate.Length(min=1, max=80))
    first_name = fields.Str(required=True)
    last_name = fields.Str(required=True)
    preferred_name = fields.Str(required=False, allow_none=True)
    email = fields.Email(required=True)
    phone = fields.Str(required=False, allow_none=True)
    date_of_birth = fields.Date(required=False, allow_none=True)
    national_identifier_last4 = fields.Str(required=False, allow_none=True)
    hire_date = fields.Date(required=True)
    termination_date = fields.Date(required=False, allow_none=True)
    employment_status = fields.Str(required=False, validate=validate.OneOf(['active','probation','suspended','terminated']))
    employment_type = fields.Str(required=False, validate=validate.OneOf(['full_time','part_time','contractor','intern','temporary']))
    job_title = fields.Str(required=False, allow_none=True)
    department_id = fields.UUID(required=False, allow_none=True)
    manager_id = fields.UUID(required=False, allow_none=True)
    work_location = fields.Str(required=False, allow_none=True)
    address = fields.Str(required=False, allow_none=True)
    external_hris_id = fields.Str(required=False, allow_none=True)


class EmployeeUpdateSchema(EmployeeCreateSchema):
    employee_number = fields.Str(required=False, validate=validate.Length(min=1, max=80))
    first_name = fields.Str(required=False)
    last_name = fields.Str(required=False)
    email = fields.Email(required=False)
    hire_date = fields.Date(required=False)
    change_effective_date = fields.Date(required=False, allow_none=True)
    change_reason = fields.Str(required=False, allow_none=True, validate=validate.Length(max=255))
