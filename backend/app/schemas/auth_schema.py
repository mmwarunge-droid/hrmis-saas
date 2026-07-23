from marshmallow import Schema, fields, validate


class RegisterSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    email = fields.Email(required=True)
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    password = fields.Str(required=True, load_only=True, validate=validate.Length(min=10, max=128))
    roles = fields.List(fields.Str(), required=False)


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)


class RefreshSchema(Schema):
    refresh_token = fields.Str(required=True)


class ForgotPasswordSchema(Schema):
    email = fields.Email(required=True)


class ResetPasswordSchema(Schema):
    token = fields.Str(required=True, validate=validate.Length(min=20, max=512))
    password = fields.Str(required=True, load_only=True, validate=validate.Length(min=10, max=128))


class VerifyEmailSchema(Schema):
    token = fields.Str(required=True, validate=validate.Length(min=20, max=512))
