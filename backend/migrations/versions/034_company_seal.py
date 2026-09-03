"""Add post-signature company seal workflow.

Revision ID: 034_company_seal
Revises: 033_checkbox_marks
"""

from alembic import op
import sqlalchemy as sa

from app.models.base import GUID


revision = '034_company_seal'
down_revision = '033_checkbox_marks'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'signature_requests',
        sa.Column(
            'seal_required',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'seal_status',
            sa.String(length=30),
            nullable=False,
            server_default='not_required',
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'sealed_at',
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.add_column(
        'signature_requests',
        sa.Column(
            'sealed_by_id',
            GUID(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        'fk_signature_requests_sealed_by_id_users',
        'signature_requests',
        'users',
        ['sealed_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_signature_requests_seal_status',
        'signature_requests',
        ['seal_status'],
        unique=False,
    )
    op.create_index(
        'ix_signature_requests_sealed_by_id',
        'signature_requests',
        ['sealed_by_id'],
        unique=False,
    )

    op.create_check_constraint(
        'ck_signature_requests_seal_status',
        'signature_requests',
        (
            "seal_status IN ("
            "'not_required','awaiting_signatures',"
            "'pending','applied'"
            ")"
        ),
    )
    op.create_check_constraint(
        'ck_signature_requests_seal_required_status',
        'signature_requests',
        (
            "("
            "seal_required = false "
            "AND seal_status = 'not_required'"
            ") OR ("
            "seal_required = true "
            "AND seal_status IN ("
            "'awaiting_signatures','pending','applied'"
            ")"
            ")"
        ),
    )
    op.create_check_constraint(
        'ck_signature_requests_sealed_at',
        'signature_requests',
        (
            "("
            "seal_status = 'applied' "
            "AND sealed_at IS NOT NULL"
            ") OR ("
            "seal_status <> 'applied' "
            "AND sealed_at IS NULL"
            ")"
        ),
    )

    op.drop_constraint(
        'ck_signature_artifacts_type',
        'signature_artifacts',
        type_='check',
    )
    op.create_check_constraint(
        'ck_signature_artifacts_type',
        'signature_artifacts',
        (
            "artifact_type IN ("
            "'original_document','signed_document',"
            "'sealed_document','audit_trail',"
            "'completion_certificate'"
            ")"
        ),
    )

    op.create_table(
        'signature_seals',
        sa.Column(
            'id',
            GUID(),
            nullable=False,
        ),
        sa.Column(
            'tenant_id',
            GUID(),
            nullable=False,
        ),
        sa.Column(
            'signature_request_id',
            GUID(),
            nullable=False,
        ),
        sa.Column(
            'uploaded_by_id',
            GUID(),
            nullable=True,
        ),
        sa.Column(
            'applied_by_id',
            GUID(),
            nullable=True,
        ),
        sa.Column(
            'sealed_artifact_id',
            GUID(),
            nullable=True,
        ),
        sa.Column(
            'image_original_filename',
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            'image_stored_filename',
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            'image_file_path',
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            'image_mime_type',
            sa.String(length=120),
            nullable=False,
        ),
        sa.Column(
            'image_size_bytes',
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            'image_sha256',
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            'page_number',
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            'x',
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            'y',
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            'width',
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            'height',
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            'uploaded_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            'applied_at',
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['signature_request_id'],
            ['signature_requests.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['uploaded_by_id'],
            ['users.id'],
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['applied_by_id'],
            ['users.id'],
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['sealed_artifact_id'],
            ['signature_artifacts.id'],
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'signature_request_id',
            name='uq_signature_seals_request',
        ),
        sa.UniqueConstraint(
            'sealed_artifact_id',
            name='uq_signature_seals_artifact',
        ),
        sa.UniqueConstraint(
            'image_stored_filename',
            name='uq_signature_seals_image_stored_filename',
        ),
        sa.CheckConstraint(
            "image_mime_type IN ("
            "'image/png','image/jpeg','image/webp'"
            ")",
            name='ck_signature_seals_image_mime',
        ),
        sa.CheckConstraint(
            'image_size_bytes >= 0',
            name='ck_signature_seals_image_size',
        ),
        sa.CheckConstraint(
            'page_number IS NULL OR page_number >= 1',
            name='ck_signature_seals_page',
        ),
        sa.CheckConstraint(
            'x IS NULL OR (x >= 0 AND x <= 1)',
            name='ck_signature_seals_x',
        ),
        sa.CheckConstraint(
            'y IS NULL OR (y >= 0 AND y <= 1)',
            name='ck_signature_seals_y',
        ),
        sa.CheckConstraint(
            'width IS NULL OR (width > 0 AND width <= 1)',
            name='ck_signature_seals_width',
        ),
        sa.CheckConstraint(
            'height IS NULL OR (height > 0 AND height <= 1)',
            name='ck_signature_seals_height',
        ),
        sa.CheckConstraint(
            'x IS NULL OR width IS NULL OR x + width <= 1',
            name='ck_signature_seals_horizontal_bounds',
        ),
        sa.CheckConstraint(
            'y IS NULL OR height IS NULL OR y + height <= 1',
            name='ck_signature_seals_vertical_bounds',
        ),
        sa.CheckConstraint(
            "("
            "applied_at IS NULL "
            "AND sealed_artifact_id IS NULL"
            ") OR ("
            "applied_at IS NOT NULL "
            "AND sealed_artifact_id IS NOT NULL"
            ")",
            name='ck_signature_seals_application_state',
        ),
    )

    op.create_index(
        'ix_signature_seals_tenant_id',
        'signature_seals',
        ['tenant_id'],
        unique=False,
    )
    op.create_index(
        'ix_signature_seals_signature_request_id',
        'signature_seals',
        ['signature_request_id'],
        unique=False,
    )
    op.create_index(
        'ix_signature_seals_uploaded_by_id',
        'signature_seals',
        ['uploaded_by_id'],
        unique=False,
    )
    op.create_index(
        'ix_signature_seals_applied_by_id',
        'signature_seals',
        ['applied_by_id'],
        unique=False,
    )
    op.create_index(
        'ix_signature_seals_image_sha256',
        'signature_seals',
        ['image_sha256'],
        unique=False,
    )
    op.create_index(
        'ix_signature_seals_uploaded_at',
        'signature_seals',
        ['uploaded_at'],
        unique=False,
    )
    op.create_index(
        'ix_signature_seals_applied_at',
        'signature_seals',
        ['applied_at'],
        unique=False,
    )


def downgrade():
    bind = op.get_bind()

    seal_rows = bind.execute(
        sa.text(
            'SELECT COUNT(*) FROM signature_seals'
        )
    ).scalar()

    sealed_artifacts = bind.execute(
        sa.text(
            "SELECT COUNT(*) "
            "FROM signature_artifacts "
            "WHERE artifact_type = 'sealed_document'"
        )
    ).scalar()

    seal_requests = bind.execute(
        sa.text(
            "SELECT COUNT(*) "
            "FROM signature_requests "
            "WHERE seal_required = true "
            "OR seal_status <> 'not_required' "
            "OR sealed_at IS NOT NULL "
            "OR sealed_by_id IS NOT NULL"
        )
    ).scalar()

    if seal_rows or sealed_artifacts or seal_requests:
        raise RuntimeError(
            'Cannot downgrade 034_company_seal while '
            'company-seal workflow data exists.'
        )

    op.drop_table('signature_seals')

    op.drop_constraint(
        'ck_signature_artifacts_type',
        'signature_artifacts',
        type_='check',
    )
    op.create_check_constraint(
        'ck_signature_artifacts_type',
        'signature_artifacts',
        (
            "artifact_type IN ("
            "'original_document','signed_document',"
            "'audit_trail','completion_certificate'"
            ")"
        ),
    )

    op.drop_constraint(
        'ck_signature_requests_sealed_at',
        'signature_requests',
        type_='check',
    )
    op.drop_constraint(
        'ck_signature_requests_seal_required_status',
        'signature_requests',
        type_='check',
    )
    op.drop_constraint(
        'ck_signature_requests_seal_status',
        'signature_requests',
        type_='check',
    )

    op.drop_index(
        'ix_signature_requests_sealed_by_id',
        table_name='signature_requests',
    )
    op.drop_index(
        'ix_signature_requests_seal_status',
        table_name='signature_requests',
    )

    op.drop_constraint(
        'fk_signature_requests_sealed_by_id_users',
        'signature_requests',
        type_='foreignkey',
    )

    op.drop_column(
        'signature_requests',
        'sealed_by_id',
    )
    op.drop_column(
        'signature_requests',
        'sealed_at',
    )
    op.drop_column(
        'signature_requests',
        'seal_status',
    )
    op.drop_column(
        'signature_requests',
        'seal_required',
    )
