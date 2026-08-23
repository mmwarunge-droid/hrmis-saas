"""add account token target email

Revision ID: 025_account_token_target_email
Revises: 024_signature_discussion
Create Date: 2026-08-23 05:13:17.379438
"""
from alembic import op
import sqlalchemy as sa


revision = '025_account_token_target_email'
down_revision = '024_signature_discussion'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'account_tokens',
        sa.Column('target_email', sa.String(length=255), nullable=True),
    )


def downgrade():
    op.drop_column('account_tokens', 'target_email')
