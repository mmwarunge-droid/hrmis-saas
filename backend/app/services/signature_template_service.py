"""Reusable placements store signer roles, never prior signer identities or answers."""

from io import BytesIO
from pathlib import Path
import hashlib

from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from werkzeug.datastructures import FileStorage
from app.extensions import db
from app.models import Document, Employee
from app.schemas.signature_schema import SignatureFieldCreateSchema
from app.utils.file_storage import save_document_file


class TemplateRoleSchema(Schema):
    role_label = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    sequence = fields.Int(load_default=1, validate=validate.Range(min=1, max=50))
    fields = fields.List(fields.Nested(SignatureFieldCreateSchema), load_default=list, validate=validate.Length(max=20))


class TemplateDefinitionSchema(Schema):
    employee_role_index = fields.Int(load_default=0, validate=validate.Range(min=0, max=49))
    subject = fields.Str(required=True, validate=validate.Length(min=2, max=220))
    message = fields.Str(load_default="", validate=validate.Length(max=5000))
    signing_mode = fields.Str(load_default="sequential", validate=validate.OneOf(["sequential", "parallel"]))
    field_placement_mode = fields.Str(load_default="document", validate=validate.OneOf(["document", "appendix"]))
    recipients = fields.List(fields.Nested(TemplateRoleSchema), required=True, validate=validate.Length(min=1, max=50))

    @validates_schema
    def validate_employee_role(self, data, **kwargs):
        if data.get("employee_role_index", 0) >= len(data.get("recipients", [])):
            raise ValidationError({"employee_role_index": ["Select a configured signer role."]})


class TemplateCreateSchema(Schema):
    tenant_id = fields.UUID(allow_none=True)
    name = fields.Str(required=True, validate=validate.Length(min=2, max=220))
    document_id = fields.UUID(required=True)
    definition = fields.Nested(TemplateDefinitionSchema, required=True)


def template_source(document):
    if document.executed_artifact_id:
        raise ValueError("Use an unsigned source document for a template.")
    content = Path(document.file_path).read_bytes()
    return content, hashlib.sha256(content).hexdigest()


def instantiate_template(template, employee_id, actor):
    employee = Employee.query.filter_by(id=employee_id, tenant_id=template.tenant_id, deleted_at=None).first()
    if not employee:
        raise ValueError("Select an employee in this organization.")
    source = template.document
    content, checksum = template_source(source)
    if checksum != template.source_checksum or source.deleted_at:
        raise ValueError("The template source changed. Save a new template version before sending.")
    stored = save_document_file(
        FileStorage(stream=BytesIO(content), filename=source.original_filename, content_type=source.mime_type),
        template.tenant_id,
    )
    document = Document(
        tenant_id=template.tenant_id,
        employee_id=employee.id,
        uploaded_by_id=actor.id,
        title=f"{template.name} — {employee.full_name}"[:220],
        document_type=source.document_type,
        checksum_sha256=checksum,
        access_level="employee",
        **stored,
    )
    db.session.add(document)
    db.session.commit()
    return document
