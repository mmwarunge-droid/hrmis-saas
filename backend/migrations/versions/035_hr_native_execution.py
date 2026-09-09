"""HR-native signing configuration, templates, executed files and retention.

Revision ID: 035_hr_native_execution
Revises: 034_company_seal
"""

from alembic import op
import sqlalchemy as sa
from app.models.base import GUID

revision = "035_hr_native_execution"
down_revision = "034_company_seal"
branch_labels = None
depends_on = None


def install_retention(bind):
    # Database enforcement covers raw SQL and cascades, not only ORM writes.
    dialect = bind.dialect.name
    if dialect == "postgresql":
        bind.execute(
            sa.text("""CREATE FUNCTION reject_signing_evidence_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Signing evidence is immutable'; END; $$""")
        )
        for table in ("signature_events", "signature_artifacts"):
            bind.execute(
                sa.text(
                    f"CREATE TRIGGER retain_{table} BEFORE UPDATE OR DELETE ON {table} "
                    "FOR EACH ROW EXECUTE FUNCTION reject_signing_evidence_mutation()"
                )
            )
        bind.execute(
            sa.text(
                "CREATE TRIGGER retain_executed_documents BEFORE UPDATE OR DELETE ON documents "
                "FOR EACH ROW WHEN (OLD.executed_artifact_id IS NOT NULL) EXECUTE FUNCTION reject_signing_evidence_mutation()"
            )
        )
        bind.execute(
            sa.text(
                "CREATE TRIGGER retain_completed_fields BEFORE UPDATE OR DELETE ON signature_fields "
                "FOR EACH ROW WHEN (OLD.completed_at IS NOT NULL) EXECUTE FUNCTION reject_signing_evidence_mutation()"
            )
        )
    elif dialect == "sqlite":
        for table, condition in [
            ("signature_events", ""),
            ("signature_artifacts", ""),
            ("documents", "WHEN OLD.executed_artifact_id IS NOT NULL"),
            ("signature_fields", "WHEN OLD.completed_at IS NOT NULL"),
        ]:
            for action in ("UPDATE", "DELETE"):
                bind.execute(
                    sa.text(
                        f"CREATE TRIGGER retain_{table}_{action.lower()} BEFORE {action} ON {table} {condition} "
                        "BEGIN SELECT RAISE(ABORT, 'Signing evidence is immutable'); END"
                    )
                )
    else:
        raise RuntimeError("Signing retention requires PostgreSQL or SQLite.")


def upgrade():
    op.add_column("signature_fields", sa.Column("read_only", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("signature_fields", sa.Column("default_value", sa.Text(), nullable=True))
    op.add_column("signature_recipients", sa.Column("signature_image", sa.Text(), nullable=True))
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("executed_artifact_id", GUID(), nullable=True))
        batch.create_foreign_key(
            "fk_documents_executed_artifact",
            "signature_artifacts",
            ["executed_artifact_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_table(
        "signature_templates",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(220), nullable=False),
        sa.Column("document_id", GUID(), sa.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_checksum", sa.String(64), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_signature_templates_tenant_id", "signature_templates", ["tenant_id"])
    install_retention(op.get_bind())


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("signature_events", "signature_artifacts"):
            op.execute(f"DROP TRIGGER retain_{table} ON {table}")
        op.execute("DROP TRIGGER retain_executed_documents ON documents")
        op.execute("DROP TRIGGER retain_completed_fields ON signature_fields")
        op.execute("DROP FUNCTION reject_signing_evidence_mutation()")
    elif bind.dialect.name == "sqlite":
        for table in ("signature_events", "signature_artifacts", "documents", "signature_fields"):
            for action in ("update", "delete"):
                op.execute(f"DROP TRIGGER retain_{table}_{action}")
    op.drop_table("signature_templates")
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("fk_documents_executed_artifact", type_="foreignkey")
        batch.drop_column("executed_artifact_id")
    op.drop_column("signature_recipients", "signature_image")
    op.drop_column("signature_fields", "default_value")
    op.drop_column("signature_fields", "read_only")
