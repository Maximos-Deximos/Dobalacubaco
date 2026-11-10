# Modelos ORM persistidos no banco SQLite.

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.schemas.execution import ExecutionStatus
from app.schemas.form import FieldStatus, FieldType


# Devolve a data e hora atual em UTC.
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Classe base declarativa do SQLAlchemy.
class Base(DeclarativeBase):
    pass


# Perfil local do usuário, com campos fixos e respostas personalizadas.
class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, default="default")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    full_name: Mapped[str | None] = mapped_column(String(200))
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    organization: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    postal_code: Mapped[str | None] = mapped_column(String(30))
    country: Mapped[str | None] = mapped_column(String(120))
    birth_date: Mapped[date | None] = mapped_column(Date)

    links: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    custom_answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


# Execução completa de preenchimento de um formulário.
class ExecutionModel(Base):
    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ExecutionStatus.IDLE.value, index=True
    )
    profile_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    fields: Mapped[list["ExecutionFieldModel"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
    )


# Resultado individual de cada campo dentro de uma execução.
class ExecutionFieldModel(Base):
    __tablename__ = "execution_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    field_id: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    field_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=FieldType.UNKNOWN.value
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    selector: Mapped[str] = mapped_column(Text, nullable=False)

    mapped_key: Mapped[str | None] = mapped_column(String(120))
    suggested_value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=FieldStatus.UNMAPPED.value
    )
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text)

    execution: Mapped[ExecutionModel] = relationship(back_populates="fields")
