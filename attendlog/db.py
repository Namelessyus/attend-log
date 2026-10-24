"""Account persistence and foundational classes; enrollment arrives later."""

from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, MetaData, String, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'teacher', 'student')", name="valid_role"),
        CheckConstraint("length(trim(display_name)) > 0", name="nonempty_display_name"),
        CheckConstraint("length(trim(email)) > 0", name="nonempty_email"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    display_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(16))
    password_hash: Mapped[str | None] = mapped_column(Text)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index("uq_users_email_case_insensitive", func.lower(User.email), unique=True)


class Class(Timestamps, Base):
    __tablename__ = "classes"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="nonempty_name"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TeacherInvitation(Base):
    __tablename__ = "teacher_invitations"
    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    target_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def migration_config() -> Config:
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return config


def migration_head() -> str:
    return ScriptDirectory.from_config(migration_config()).get_current_head()
