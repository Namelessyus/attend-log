"""Revocable sessions, teacher invitations, login throttling, and account audit."""
from alembic import op
import sqlalchemy as sa

revision = "0002_accounts"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    for table, ending in [("login_sessions", "revoked_at"), ("teacher_invitations", "consumed_at")]:
        op.create_table(
            table,
            sa.Column("token_digest", sa.String(64), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(ending, sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
    op.create_table(
        "login_throttles",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("target_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("security_events")
    op.drop_table("login_throttles")
    op.drop_table("teacher_invitations")
    op.drop_table("login_sessions")
