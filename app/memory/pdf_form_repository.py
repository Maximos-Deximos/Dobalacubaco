# Repositórios de sessões de PDF e da memória vetorial de campos.

from __future__ import annotations

import hashlib
import unicodedata
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from app.memory.database import session_scope
from app.memory.models import (
    PdfFieldMemoryModel,
    PdfFillFieldModel,
    PdfFillSessionModel,
    SourceModel,
)
from app.schemas.pdf import (
    PdfFieldMemory,
    PdfFieldOption,
    PdfFieldRecord,
    PdfFieldStatus,
    PdfFieldType,
    PdfFormField,
    PdfFormSession,
    PdfFormSessionDetail,
    PdfGenerationStatus,
    PdfSessionStatus,
    PdfSuggestionSource,
)


# Erro lançado quando a sessão ou o campo não existe.
class PdfFormNotFoundError(LookupError):
    pass


# Converte uma opção persistida em contrato Pydantic.
def _to_options(raw: list[Any] | None) -> list[PdfFieldOption]:
    options: list[PdfFieldOption] = []
    for item in raw or []:
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("value") or "")
            value = str(item.get("value") or label)
            if value:
                options.append(PdfFieldOption(label=label or value, value=value))
        else:
            value = str(item)
            if value:
                options.append(PdfFieldOption(label=value, value=value))
    return options


# Converte o modelo ORM no contrato do campo.
def _to_field(model: PdfFillFieldModel) -> PdfFieldRecord:
    return PdfFieldRecord(
        id=model.id,
        session_id=model.session_id,
        field_name=model.field_name,
        label=model.label,
        field_type=PdfFieldType(model.field_type),
        required=model.required,
        readonly=model.readonly,
        options=_to_options(model.options),
        current_value=model.current_value,
        suggested_value=model.suggested_value,
        final_value=model.final_value,
        confidence=model.confidence,
        rationale=model.rationale,
        suggestion_source=(
            PdfSuggestionSource(model.suggestion_source)
            if model.suggestion_source
            else None
        ),
        status=PdfFieldStatus(model.status),
        page_number=model.page_number,
        max_length=model.max_length,
        warnings=list(model.warnings or []),
        revision=model.revision,
        updated_at=model.updated_at,
    )


# Converte o modelo ORM no contrato da sessão.
def _to_session(model: PdfFillSessionModel, source_title: str = "") -> PdfFormSession:
    return PdfFormSession(
        id=model.id,
        workspace_id=model.workspace_id,
        source_id=model.source_id,
        source_title=source_title,
        instructions=model.instructions,
        status=PdfSessionStatus(model.status),
        generation_status=PdfGenerationStatus(model.generation_status),
        generation_progress=model.generation_progress,
        generation_total=model.generation_total,
        output_path=model.output_path,
        error=model.error,
        created_at=model.created_at,
        updated_at=model.updated_at,
        last_suggested_at=model.last_suggested_at,
    )


# Normaliza texto para comparação e geração de hash.
def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_text.lower().split())


# Gera o hash estável de uma memória de campo.
def memory_hash(
    *,
    workspace_id: int,
    label: str,
    field_name: str,
    field_type: str,
    value: str,
) -> str:
    payload = "|".join(
        [
            str(workspace_id),
            normalize_text(label or field_name),
            str(field_type),
            normalize_text(value),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Repositório das sessões e dos campos de formulários PDF.
class PdfFormRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    # Cria a sessão e persiste os campos inspecionados.
    def create_session(
        self,
        *,
        workspace_id: int,
        source_id: int,
        instructions: str,
        fields: list[PdfFormField],
    ) -> PdfFormSessionDetail:
        with session_scope(self.database_url) as session:
            model = PdfFillSessionModel(
                workspace_id=workspace_id,
                source_id=source_id,
                instructions=instructions,
                status=PdfSessionStatus.DRAFT.value,
                generation_status=PdfGenerationStatus.IDLE.value,
                generation_progress=0,
                generation_total=len(fields),
            )
            session.add(model)
            session.flush()

            for field in fields:
                session.add(
                    PdfFillFieldModel(
                        session_id=model.id,
                        field_name=field.field_name,
                        label=field.label,
                        field_type=field.field_type.value,
                        required=field.required,
                        readonly=field.readonly,
                        options=[option.model_dump() for option in field.options],
                        current_value=field.current_value,
                        status=PdfFieldStatus.PENDING.value,
                        page_number=field.page_number,
                        max_length=field.max_length,
                        warnings=list(field.warnings),
                        revision=0,
                    )
                )

            session.flush()
            source = session.get(SourceModel, source_id)
            title = source.title if source is not None else ""
            return PdfFormSessionDetail(
                **_to_session(model, title).model_dump(),
                fields=[_to_field(field) for field in model.fields],
            )

    # Busca a sessão mais recente ainda aberta para uma fonte.
    def find_latest_open(self, source_id: int) -> PdfFormSessionDetail | None:
        with session_scope(self.database_url) as session:
            model = session.scalar(
                select(PdfFillSessionModel)
                .where(PdfFillSessionModel.source_id == source_id)
                .where(
                    PdfFillSessionModel.status.not_in(
                        [
                            PdfSessionStatus.FILLED.value,
                            PdfSessionStatus.FAILED.value,
                        ]
                    )
                )
                .order_by(PdfFillSessionModel.id.desc())
                .limit(1)
            )
            return self._detail(session, model) if model is not None else None

    # Busca a sessão mais recente, mesmo já preenchida.
    def find_latest(self, source_id: int) -> PdfFormSessionDetail | None:
        with session_scope(self.database_url) as session:
            model = session.scalar(
                select(PdfFillSessionModel)
                .where(PdfFillSessionModel.source_id == source_id)
                .order_by(PdfFillSessionModel.id.desc())
                .limit(1)
            )
            return self._detail(session, model) if model is not None else None

    # Busca uma sessão pelo identificador.
    def get_session(self, session_id: int) -> PdfFormSessionDetail:
        with session_scope(self.database_url) as session:
            model = session.get(PdfFillSessionModel, session_id)
            if model is None:
                raise PdfFormNotFoundError(
                    f"Sessão de preenchimento {session_id} não encontrada."
                )
            return self._detail(session, model)

    # Busca um campo específico de uma sessão.
    def get_field(self, session_id: int, field_name: str) -> PdfFieldRecord:
        with session_scope(self.database_url) as session:
            model = session.scalar(
                select(PdfFillFieldModel)
                .where(PdfFillFieldModel.session_id == session_id)
                .where(PdfFillFieldModel.field_name == field_name)
            )
            if model is None:
                raise PdfFormNotFoundError(
                    f"Campo '{field_name}' não encontrado na sessão {session_id}."
                )
            return _to_field(model)

    # Atualiza dados gerais da sessão.
    def update_session(self, session_id: int, **changes: Any) -> PdfFormSessionDetail:
        allowed = {
            "status",
            "generation_status",
            "generation_progress",
            "generation_total",
            "output_path",
            "error",
            "instructions",
            "last_suggested_at",
        }
        with session_scope(self.database_url) as session:
            model = session.get(PdfFillSessionModel, session_id)
            if model is None:
                raise PdfFormNotFoundError(
                    f"Sessão de preenchimento {session_id} não encontrada."
                )
            for key, value in changes.items():
                if key not in allowed:
                    continue
                if hasattr(value, "value"):
                    value = value.value
                setattr(model, key, value)
            session.flush()
            return self._detail(session, model)

    # Atualiza um campo com controle otimista de revisão.
    def update_field(
        self,
        session_id: int,
        field_name: str,
        *,
        expected_revision: int | None = None,
        increment_revision: bool = False,
        **changes: Any,
    ) -> PdfFieldRecord | None:
        allowed = {
            "label",
            "field_type",
            "required",
            "readonly",
            "options",
            "current_value",
            "suggested_value",
            "final_value",
            "confidence",
            "rationale",
            "suggestion_source",
            "status",
            "page_number",
            "max_length",
            "warnings",
        }
        with session_scope(self.database_url) as session:
            model = session.scalar(
                select(PdfFillFieldModel)
                .where(PdfFillFieldModel.session_id == session_id)
                .where(PdfFillFieldModel.field_name == field_name)
            )
            if model is None:
                raise PdfFormNotFoundError(
                    f"Campo '{field_name}' não encontrado na sessão {session_id}."
                )
            if expected_revision is not None and model.revision != expected_revision:
                return None

            for key, value in changes.items():
                if key not in allowed:
                    continue
                if key == "options":
                    value = [
                        option.model_dump() if hasattr(option, "model_dump") else option
                        for option in (value or [])
                    ]
                if hasattr(value, "value"):
                    value = value.value
                setattr(model, key, value)

            if increment_revision:
                model.revision += 1
            session.flush()
            return _to_field(model)

    # Marca uma sessão como preenchida.
    def mark_filled(
        self,
        session_id: int,
        *,
        output_path: str,
        field_names: list[str],
    ) -> PdfFormSessionDetail:
        with session_scope(self.database_url) as session:
            model = session.get(PdfFillSessionModel, session_id)
            if model is None:
                raise PdfFormNotFoundError(
                    f"Sessão de preenchimento {session_id} não encontrada."
                )
            model.status = PdfSessionStatus.FILLED.value
            model.output_path = output_path
            model.error = None
            for field in model.fields:
                if field.field_name in field_names:
                    field.status = PdfFieldStatus.FILLED.value
            session.flush()
            return self._detail(session, model)

    # Converte uma sessão e seus campos.
    def _detail(
        self,
        session,
        model: PdfFillSessionModel,
    ) -> PdfFormSessionDetail:
        source = session.get(SourceModel, model.source_id)
        return PdfFormSessionDetail(
            **_to_session(model, source.title if source is not None else "").model_dump(),
            fields=[_to_field(field) for field in model.fields],
        )


# Repositório da memória vetorial de valores aprovados.
class PdfMemoryRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    # Insere ou incrementa o uso de uma memória aprovada.
    def upsert(
        self,
        *,
        workspace_id: int,
        source_id: int | None,
        label: str,
        field_name: str,
        field_type: str,
        value: str,
        embedding: list[float] | None,
        embedding_model: str | None,
    ) -> PdfFieldMemory:
        digest = memory_hash(
            workspace_id=workspace_id,
            label=label,
            field_name=field_name,
            field_type=field_type,
            value=value,
        )
        with session_scope(self.database_url) as session:
            model = session.scalar(
                select(PdfFieldMemoryModel)
                .where(PdfFieldMemoryModel.workspace_id == workspace_id)
                .where(PdfFieldMemoryModel.memory_hash == digest)
            )
            if model is None:
                model = PdfFieldMemoryModel(
                    workspace_id=workspace_id,
                    source_id=source_id,
                    memory_hash=digest,
                    label=label,
                    field_name=field_name,
                    field_type=field_type,
                    value=value,
                    embedding=embedding,
                    embedding_model=embedding_model if embedding else None,
                    embedding_dim=len(embedding) if embedding else None,
                    usage_count=1,
                    approved=True,
                )
                session.add(model)
            else:
                model.usage_count += 1
                model.source_id = source_id
                model.approved = True
                if embedding:
                    model.embedding = embedding
                    model.embedding_model = embedding_model
                    model.embedding_dim = len(embedding)
            session.flush()
            return self._to_schema(model)

    # Lista memórias do workspace, opcionalmente apenas com embeddings.
    def list_by_workspace(
        self,
        workspace_id: int,
        *,
        only_embedded: bool = False,
        embedding_model: str | None = None,
    ) -> list[PdfFieldMemory]:
        statement = (
            select(PdfFieldMemoryModel)
            .where(PdfFieldMemoryModel.workspace_id == workspace_id)
            .order_by(PdfFieldMemoryModel.id)
        )
        if only_embedded:
            statement = statement.where(
                PdfFieldMemoryModel.embedding_model.is_not(None)
            )
        if embedding_model is not None:
            statement = statement.where(
                PdfFieldMemoryModel.embedding_model == embedding_model
            )
        with session_scope(self.database_url) as session:
            models = session.scalars(statement).all()
            return [self._to_schema(model) for model in models]

    # Conta memórias totais e com embedding.
    def count_by_workspace(self, workspace_id: int) -> tuple[int, int]:
        with session_scope(self.database_url) as session:
            total = session.scalar(
                select(func.count(PdfFieldMemoryModel.id)).where(
                    PdfFieldMemoryModel.workspace_id == workspace_id
                )
            )
            embedded = session.scalar(
                select(func.count(PdfFieldMemoryModel.id))
                .where(PdfFieldMemoryModel.workspace_id == workspace_id)
                .where(PdfFieldMemoryModel.embedding_model.is_not(None))
            )
            return int(total or 0), int(embedded or 0)

    # Converte o modelo ORM em contrato de memória.
    def _to_schema(self, model: PdfFieldMemoryModel) -> PdfFieldMemory:
        return PdfFieldMemory(
            id=model.id,
            workspace_id=model.workspace_id,
            source_id=model.source_id,
            label=model.label,
            field_name=model.field_name,
            field_type=PdfFieldType(model.field_type),
            value=model.value,
            embedding=list(model.embedding) if model.embedding is not None else None,
            embedding_model=model.embedding_model,
            embedding_dim=model.embedding_dim,
            usage_count=model.usage_count,
            approved=model.approved,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


# Devolve o instante atual em UTC.
def utcnow() -> datetime:
    return datetime.now(UTC)
