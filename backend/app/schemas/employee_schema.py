from marshmallow import Schema, fields, validate


class DepartmentSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=2, max=140))
    code = fields.Str(required=False, allow_none=True)
    parent_department_id = fields.UUID(required=False, allow_none=True)


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
