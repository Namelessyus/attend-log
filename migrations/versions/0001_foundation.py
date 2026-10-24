"""Create soft-deletable users and classes; no authentication endpoints yet."""
from alembic import op
import sqlalchemy as sa

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.CheckConstraint("role IN ('admin', 'teacher', 'student')", name="ck_users_valid_role"),
        sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_users_nonempty_display_name"),
        sa.CheckConstraint("length(trim(email)) > 0", name="ck_users_nonempty_email"),
    )
    op.create_index("uq_users_email_case_insensitive", "users", [sa.text("lower(email)")], unique=True)
    op.create_table(
        "classes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *timestamps(),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_classes_nonempty_name"),
    )


def downgrade():
    op.drop_table("classes")
    op.drop_index("uq_users_email_case_insensitive", table_name="users")
    op.drop_table("users")
