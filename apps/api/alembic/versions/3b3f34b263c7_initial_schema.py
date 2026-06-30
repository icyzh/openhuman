"""initial schema

Revision ID: 3b3f34b263c7
Revises:
Create Date: 2026-06-30 19:09:38.478305
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "3b3f34b263c7"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create fresh schema — drop old tables first, then create ours."""
    # Drop old tables (CASCADE handles FK dependencies from the old TypeScript schema)
    op.execute("DROP TABLE IF EXISTS verification CASCADE")
    op.execute("DROP TABLE IF EXISTS session CASCADE")
    op.execute("DROP TABLE IF EXISTS account CASCADE")
    op.execute("DROP TABLE IF EXISTS activity_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS memory_review_candidates CASCADE")
    op.execute("DROP TABLE IF EXISTS memory_review_events CASCADE")
    op.execute("DROP TABLE IF EXISTS memory_review_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS people CASCADE")
    op.execute("DROP TABLE IF EXISTS documents CASCADE")
    op.execute("DROP TABLE IF EXISTS channel_assignments CASCADE")
    op.execute("DROP TABLE IF EXISTS employees CASCADE")
    op.execute("DROP TABLE IF EXISTS organizations CASCADE")
    op.execute('DROP TABLE IF EXISTS "user" CASCADE')

    # Create tables in FK order
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("cognee_tenant_id", sa.String(length=255), nullable=True),
        sa.Column("cognee_tenant_name", sa.String(length=255), nullable=True),
        sa.Column("cognee_system_user_id", sa.String(length=255), nullable=True),
        sa.Column("cognee_system_user_name", sa.String(length=255), nullable=True),
        sa.Column("cognee_dataset_id", sa.String(length=255), nullable=True),
        sa.Column("cognee_dataset_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "employees",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=255), nullable=True),
        sa.Column("personality", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("specialization", sa.String(length=255), nullable=True),
        sa.Column("duties", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("discord_token_enc", sa.Text(), nullable=True),
        sa.Column("slack_token_enc", sa.Text(), nullable=True),
        sa.Column("mcp_connections", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("memory_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cognee_user_id", sa.String(length=255), nullable=True),
        sa.Column("cognee_user_name", sa.String(length=255), nullable=True),
        sa.Column("cognee_dataset_id", sa.String(length=255), nullable=True),
        sa.Column("cognee_dataset_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="inactive", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employees_org_id", "employees", ["org_id"], unique=False)

    op.create_table(
        "channel_assignments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("channel_id", sa.String(length=255), nullable=False),
        sa.Column("channel_name", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_channel_assignments_employee_id", "channel_assignments", ["employee_id"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("storage_path", sa.String(length=500), nullable=True),
        sa.Column("cognee_document_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="uploaded", nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop all tables in reverse FK order."""
    op.execute("DROP TABLE IF EXISTS documents CASCADE")
    op.execute("DROP TABLE IF EXISTS channel_assignments CASCADE")
    op.execute("DROP TABLE IF EXISTS employees CASCADE")
    op.execute("DROP TABLE IF EXISTS organizations CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
