"""tighten onboarding role boundaries

Revision ID: 022_security_workflow_boundaries
Revises: 021_workflow_hardening
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa


revision = '022_security_workflow_boundaries'
down_revision = '021_workflow_hardening'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text(
        """
        INSERT INTO permissions (
            id,
            code,
            description,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            'onboarding:self',
            'Access personal onboarding work',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        WHERE NOT EXISTS (
            SELECT 1 FROM permissions
            WHERE code = 'onboarding:self'
        )
        """
    ))

    for role_name in ('EMPLOYEE', 'MANAGER'):
        op.execute(sa.text(
            """
            INSERT INTO role_permissions (
                id,
                role_id,
                permission_id,
                created_at,
                updated_at
            )
            SELECT
                gen_random_uuid(),
                role.id,
                permission.id,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM roles AS role
            CROSS JOIN permissions AS permission
            WHERE role.name = :role_name
              AND permission.code = 'onboarding:self'
              AND NOT EXISTS (
                SELECT 1
                FROM role_permissions AS existing
                WHERE existing.role_id = role.id
                  AND existing.permission_id = permission.id
              )
            """
        ).bindparams(role_name=role_name))

    op.execute(sa.text(
        """
        DELETE FROM role_permissions
        WHERE role_id IN (
            SELECT id FROM roles WHERE name = 'EMPLOYEE'
        )
          AND permission_id IN (
            SELECT id FROM permissions
            WHERE code = 'onboarding:assign'
        )
        """
    ))


def downgrade():
    op.execute(sa.text(
        """
        INSERT INTO role_permissions (
            id,
            role_id,
            permission_id,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            role.id,
            permission.id,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM roles AS role
        CROSS JOIN permissions AS permission
        WHERE role.name = 'EMPLOYEE'
          AND permission.code = 'onboarding:assign'
          AND NOT EXISTS (
            SELECT 1
            FROM role_permissions AS existing
            WHERE existing.role_id = role.id
              AND existing.permission_id = permission.id
          )
        """
    ))

    op.execute(sa.text(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions
            WHERE code = 'onboarding:self'
        )
        """
    ))
    op.execute(sa.text(
        "DELETE FROM permissions WHERE code = 'onboarding:self'"
    ))
