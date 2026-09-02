from marshmallow import Schema, fields


class NormalizedEmail(fields.Email):
    """Email field that applies Kinetic's canonical identity normalization."""

    def _deserialize(self, value, attr, data, **kwargs):
        if isinstance(value, str):
            value = value.strip().lower()
        return super()._deserialize(value, attr, data, **kwargs)


class EmailAvailabilitySchema(Schema):
    email = NormalizedEmail(required=True)
    tenant_id = fields.UUID(required=False, allow_none=True)
