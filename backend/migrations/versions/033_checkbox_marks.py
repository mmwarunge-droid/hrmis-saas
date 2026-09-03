"""Add checkbox signing marks.

Revision ID: 033_checkbox_marks
Revises: 032_signing_fields_v2
"""

from alembic import op
import sqlalchemy as sa


revision = '033_checkbox_marks'
down_revision = '032_signing_fields_v2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'signature_fields',
        sa.Column(
            'mark_style',
            sa.String(length=12),
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
        (
            "field_type IN ("
            "'signature','date','text','name','initials','checkbox'"
            ")"
        ),
    )

    op.create_check_constraint(
        'ck_signature_fields_mark_style',
        'signature_fields',
        (
            "("
            "field_type = 'checkbox' AND "
            "mark_style IN ('tick','cross','either')"
            ") OR ("
            "field_type <> 'checkbox' AND "
            "mark_style IS NULL"
            ")"
        ),
    )


def downgrade():
    bind = op.get_bind()

    checkbox_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) "
            "FROM signature_fields "
            "WHERE field_type = 'checkbox'"
        )
    ).scalar_one()

    if checkbox_count:
        raise RuntimeError(
            'Cannot downgrade 033_checkbox_marks while '
            'checkbox signing fields exist.'
        )

    op.drop_constraint(
        'ck_signature_fields_mark_style',
        'signature_fields',
        type_='check',
    )

    op.drop_constraint(
        'ck_signature_fields_type',
        'signature_fields',
        type_='check',
    )

    op.create_check_constraint(
        'ck_signature_fields_type',
        'signature_fields',
        (
            "field_type IN ("
            "'signature','date','text','name','initials'"
            ")"
        ),
    )

    op.drop_column(
        'signature_fields',
        'mark_style',
    )
