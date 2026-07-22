from marshmallow import Schema, fields, validate


class DocumentUploadSchema(Schema):
    tenant_id = fields.UUID(required=False, allow_none=True)
    employee_id = fields.UUID(required=False, allow_none=True)
    title = fields.Str(required=True, validate=validate.Length(min=2, max=220))
    document_type = fields.Str(required=True, validate=validate.OneOf(['contract', 'policy', 'tax', 'certification', 'id', 'other']))
    expiry_date = fields.Date(required=False, allow_none=True)
    issued_date = fields.Date(required=False, allow_none=True)
    signature_status = fields.Str(required=False, validate=validate.OneOf(['not_required','pending','signed','declined','expired']))
    access_level = fields.Str(required=False, validate=validate.OneOf(['employee','manager','hr_only','company_admin']))


class DocumentUpdateSchema(Schema):
    title = fields.Str(required=False)
    document_type = fields.Str(required=False, validate=validate.OneOf(['contract', 'policy', 'tax', 'certification', 'id', 'other']))
    expiry_date = fields.Date(required=False, allow_none=True)
    issued_date = fields.Date(required=False, allow_none=True)
    signature_status = fields.Str(required=False, validate=validate.OneOf(['not_required','pending','signed','declined','expired']))
    access_level = fields.Str(required=False, validate=validate.OneOf(['employee','manager','hr_only','company_admin']))
    status = fields.Str(required=False, validate=validate.OneOf(['active','archived','expired','pending_review']))
