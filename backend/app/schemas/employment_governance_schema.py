from marshmallow import Schema, fields, validate


class EmploymentGovernanceSchema(Schema):
    duplicate_job_title_warning_titles = fields.List(
        fields.Str(validate=validate.Length(min=1, max=160)),
        required=True,
        validate=validate.Length(max=100),
    )
