from datetime import date

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.models.employee_home import DEFAULT_HOME_SECTIONS


SECTION_CHOICES = set(DEFAULT_HOME_SECTIONS)


class HomepageSettingsUpdateSchema(Schema):
    banner_url = fields.Url(required=False, allow_none=True)
    logo_url = fields.Url(required=False, allow_none=True)
    welcome_message = fields.Str(
        required=False,
        validate=validate.Length(min=1, max=240),
    )
    enabled_sections = fields.List(
        fields.Str(validate=validate.OneOf(sorted(SECTION_CHOICES))),
        required=False,
    )
    section_order = fields.List(
        fields.Str(validate=validate.OneOf(sorted(SECTION_CHOICES))),
        required=False,
    )
    new_hire_window_days = fields.Int(
        required=False,
        validate=validate.Range(min=7, max=180),
    )
    birthday_visibility_enabled = fields.Bool(required=False)
    anniversaries_enabled = fields.Bool(required=False)
    people_statistics_enabled = fields.Bool(required=False)
    assistant_enabled = fields.Bool(required=False)
    assistant_url = fields.Url(required=False, allow_none=True)


class EmployeeSelfProfileSchema(Schema):
    date_of_birth = fields.Date(required=False, allow_none=True)
    birthday_visibility = fields.Str(
        required=False,
        validate=validate.OneOf(['colleagues', 'hr_only', 'hidden']),
    )
    biography = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=2000),
    )
    hobbies = fields.List(
        fields.Str(validate=validate.Length(min=1, max=80)),
        required=False,
        validate=validate.Length(max=20),
    )
    profile_photo_url = fields.Url(required=False, allow_none=True)
    profile_cover_url = fields.Url(required=False, allow_none=True)
    gender_identity = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.OneOf([
            'woman',
            'man',
            'non_binary',
            'self_described',
            'prefer_not_to_say',
        ]),
    )
    gender_self_description = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=120),
    )

    @validates_schema
    def validate_profile(self, data, **kwargs):
        if data.get('date_of_birth') and data['date_of_birth'] > date.today():
            raise ValidationError({
                'date_of_birth': ['Date of birth cannot be in the future.'],
            })
        if (
            data.get('gender_identity') == 'self_described'
            and not data.get('gender_self_description')
        ):
            raise ValidationError({
                'gender_self_description': [
                    'Add a description when self-described is selected.',
                ],
            })


class OrganizationEventCreateSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=2, max=180))
    description = fields.Str(required=False, allow_none=True)
    starts_at = fields.DateTime(required=True)
    ends_at = fields.DateTime(required=False, allow_none=True)
    location = fields.Str(required=False, allow_none=True, validate=validate.Length(max=240))
    meeting_url = fields.Url(required=False, allow_none=True)
    image_url = fields.Url(required=False, allow_none=True)
    audience = fields.Str(
        required=False,
        load_default='all',
        validate=validate.OneOf(['all', 'employees', 'managers']),
    )
    status = fields.Str(
        required=False,
        load_default='draft',
        validate=validate.OneOf(['draft', 'published', 'cancelled']),
    )

    @validates_schema
    def validate_dates(self, data, **kwargs):
        if data.get('ends_at') and data['ends_at'] < data['starts_at']:
            raise ValidationError({'ends_at': ['End time must be after the start time.']})


class OrganizationEventUpdateSchema(OrganizationEventCreateSchema):
    title = fields.Str(required=False, validate=validate.Length(min=2, max=180))
    starts_at = fields.DateTime(required=False)

    @validates_schema
    def validate_dates(self, data, **kwargs):
        if data.get('starts_at') and data.get('ends_at') and data['ends_at'] < data['starts_at']:
            raise ValidationError({'ends_at': ['End time must be after the start time.']})


class HomepageEssentialCreateSchema(Schema):
    document_id = fields.UUID(required=True)
    display_title = fields.Str(required=False, allow_none=True, validate=validate.Length(max=180))
    display_order = fields.Int(required=False, load_default=0)
    importance = fields.Str(
        required=False,
        load_default='recommended',
        validate=validate.OneOf(['required', 'recommended']),
    )
    is_published = fields.Bool(required=False, load_default=True)


class HomepageEssentialUpdateSchema(Schema):
    display_title = fields.Str(required=False, allow_none=True, validate=validate.Length(max=180))
    display_order = fields.Int(required=False)
    importance = fields.Str(
        required=False,
        validate=validate.OneOf(['required', 'recommended']),
    )
    is_published = fields.Bool(required=False)
