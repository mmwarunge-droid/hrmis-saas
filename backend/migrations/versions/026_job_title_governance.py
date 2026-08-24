"""add duplicate job title governance

Revision ID: 026_job_title_governance
Revises: 025_account_token_target_email
Create Date: 2026-08-23
"""

from alembic import op
import sqlalchemy as sa


revision = '026_job_title_governance'
down_revision = '025_account_token_target_email'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'tenants',
        sa.Column(
            'duplicate_job_title_warning_titles',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column(
        'tenants',
        'duplicate_job_title_warning_titles',
        server_default=None,
    )


def downgrade():
    op.drop_column(
        'tenants',
        'duplicate_job_title_warning_titles',
    )
