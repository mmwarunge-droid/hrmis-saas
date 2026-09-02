"""Extend native signing fields for HR document completion.

Revision ID: 032_signing_fields_v2
Revises: 031_normalized_email_uniqueness
"""

from alembic import op
import sqlalchemy as sa


revision = '032_signing_fields_v2'
down_revision = '031_normalized_email_uniqueness'
branch_labels = None
depends_on = None


OLD_TYPES = "field_type IN ('signature','date')"

NEW_TYPES = (
    "field_type IN ("
    "'signature','date','text','name','initials'"
    ")"
)


def upgrade():
    op.add_column(
        'signature_fields',
        sa.Column(
            'placeholder',
            sa.String(length=240),
            nullable=True,
        ),
    )

    op.add_column(
        'signature_fields',
        sa.Column(
            'prefill_key',
            sa.String(length=80),
            nullable=True,
        ),
    )

    op.drop_constraint(
        'ck_signature_fields_type',
        'signature_fields',
        type_='check',
    )

    op.create_check_constraint(
        'ck_signature_fields_type',
        'signature_fields',
        NEW_TYPES,
    )


def downgrade():
    bind = op.get_bind()

    incompatible = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM signature_fields
            WHERE field_type NOT IN (
                'signature',
                'date'
            )
            """
        )
    ).scalar() or 0

    if incompatible:
        raise RuntimeError(
            'Cannot downgrade signing fields while '
            'text/name/initials fields exist.'
        )

    op.drop_constraint(
        'ck_signature_fields_type',
        'signature_fields',
        type_='check',
    )

    op.create_check_constraint(
        'ck_signature_fields_type',
        'signature_fields',
        OLD_TYPES,
    )

    op.drop_column(
        'signature_fields',
        'prefill_key',
    )

    op.drop_column(
        'signature_fields',
        'placeholder',
    )
