# Modelos ORM persistidos no banco SQLite.

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.schemas.execution import ExecutionStatus
from app.schemas.form import FieldStatus, FieldType


# Devolve a data e hora atual em UTC.
def utcnow() -> datetime:
    return datetime.now(UTC)


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

    fields: Mapped[list[ExecutionFieldModel]] = relationship(
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


# Workspace que agrupa fontes e, futuramente, a proposta de um edital.
class WorkspaceModel(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    sources: Mapped[list[SourceModel]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    proposals: Mapped[list[ProposalModel]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
    )


# Fonte pública ou arquivo local associado a um workspace.
class SourceModel(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"),
        index=True,
    )
    url: Mapped[str | None] = mapped_column(Text)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    final_url: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(String(120))
    sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    workspace: Mapped[WorkspaceModel] = relationship(back_populates="sources")
    snapshot: Mapped[SourceSnapshotModel | None] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        uselist=False,
    )
    chunks: Mapped[list[SourceChunkModel]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )


# Conteúdo bruto e texto extraído de uma fonte.
class SourceSnapshotModel(Base):
    __tablename__ = "source_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    raw_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    segments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    http_status: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    source: Mapped[SourceModel] = relationship(back_populates="snapshot")


# Trecho indexado de uma fonte para busca semântica e lexical.
class SourceChunkModel(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "chunk_index",
            name="uq_source_chunks_source_chunk",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    embedding: Mapped[list[float] | None] = mapped_column(JSON)
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    embedding_dim: Mapped[int | None] = mapped_column(Integer)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    source: Mapped[SourceModel] = relationship(back_populates="chunks")


# Proposta de solução vinculada a um workspace.
class ProposalModel(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", index=True
    )
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    workspace: Mapped[WorkspaceModel] = relationship(back_populates="proposals")
    sections: Mapped[list[ProposalSectionModel]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        order_by="ProposalSectionModel.position",
    )
    revisions: Mapped[list[ProposalRevisionModel]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        order_by="ProposalRevisionModel.id",
    )


# Seção editável de uma proposta.
class ProposalSectionModel(Base):
    __tablename__ = "proposal_sections"
    __table_args__ = (
        UniqueConstraint(
            "proposal_id",
            "key",
            name="uq_proposal_sections_proposal_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proposal_id: Mapped[int] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="empty", index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    proposal: Mapped[ProposalModel] = relationship(back_populates="sections")


# Histórico append-only das alterações de seções.
class ProposalRevisionModel(Base):
    __tablename__ = "proposal_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proposal_id: Mapped[int] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("proposal_sections.id", ondelete="SET NULL"),
        index=True,
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False, default="update")
    content_before: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_after: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actor: Mapped[str] = mapped_column(String(32), nullable=False, default="cli")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    proposal: Mapped[ProposalModel] = relationship(back_populates="revisions")


# Sessão persistida de preenchimento de um formulário PDF.
class PdfFillSessionModel(Base):
    __tablename__ = "pdf_fill_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", index=True
    )
    generation_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="idle"
    )
    generation_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_path: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    last_suggested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    fields: Mapped[list[PdfFillFieldModel]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="PdfFillFieldModel.id",
    )


# Campo individual de uma sessão de preenchimento de PDF.
class PdfFillFieldModel(Base):
    __tablename__ = "pdf_fill_fields"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "field_name",
            name="uq_pdf_fill_fields_session_field",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("pdf_fill_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    field_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown"
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    readonly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    current_value: Mapped[str | None] = mapped_column(Text)
    suggested_value: Mapped[str | None] = mapped_column(Text)
    final_value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    suggestion_source: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer)
    max_length: Mapped[int | None] = mapped_column(Integer)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    session: Mapped[PdfFillSessionModel] = relationship(back_populates="fields")


# Memória vetorial de valores de campos já revisados e aprovados.
class PdfFieldMemoryModel(Base):
    __tablename__ = "pdf_field_memories"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "memory_hash",
            name="uq_pdf_field_memories_workspace_hash",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"),
        index=True,
    )
    memory_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    field_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    field_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown"
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(JSON)
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    embedding_dim: Mapped[int | None] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
