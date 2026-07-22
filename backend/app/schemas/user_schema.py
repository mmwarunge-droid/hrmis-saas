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


class UserCreateSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    email = fields.Email(required=True)
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    password = fields.Str(required=True, validate=validate.Length(min=10, max=128), load_only=True)
    roles = fields.List(fields.Str(), required=True, validate=validate.Length(min=1))


class UserUpdateSchema(Schema):
    first_name = fields.Str(required=False)
    last_name = fields.Str(required=False)
    is_active = fields.Bool(required=False)


class UserRoleUpdateSchema(Schema):
    roles = fields.List(fields.Str(), required=True, validate=validate.Length(min=1))
