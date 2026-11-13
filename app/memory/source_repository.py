# Repositório responsável pela leitura e escrita de fontes ingeridas.

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.memory.database import session_scope
from app.memory.models import SourceModel, SourceSnapshotModel
from app.schemas.source import (
    ExtractedSegment,
    Source,
    SourceDetail,
    SourceKind,
    SourceSnapshot,
    SourceStatus,
)


# Erro lançado quando a fonte solicitada não existe.
class SourceNotFoundError(LookupError):
    pass


# Converte o modelo ORM no contrato Pydantic da fonte.
def _to_source(model: SourceModel) -> Source:
    return Source.model_validate(model)


# Converte o modelo ORM no contrato Pydantic do snapshot.
def _to_snapshot(model: SourceSnapshotModel) -> SourceSnapshot:
    return SourceSnapshot(
        id=model.id,
        source_id=model.source_id,
        raw_path=model.raw_path,
        content_text=model.content_text,
        segments=[ExtractedSegment.model_validate(item) for item in model.segments],
        metadata=dict(model.extra_metadata or {}),
        warnings=list(model.warnings or []),
        page_count=model.page_count,
        http_status=model.http_status,
        fetched_at=model.fetched_at,
    )


# Repositório de fontes e seus snapshots.
class SourceRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    # Cria uma fonte associada a um workspace.
    def create(
        self,
        *,
        workspace_id: int,
        source_kind: SourceKind,
        url: str | None = None,
        parent_source_id: int | None = None,
        title: str = "",
        final_url: str | None = None,
        content_type: str | None = None,
        sha256: str | None = None,
        status: SourceStatus = SourceStatus.PENDING,
        error: str | None = None,
    ) -> Source:
        with session_scope(self.database_url) as session:
            model = SourceModel(
                workspace_id=workspace_id,
                parent_source_id=parent_source_id,
                url=url,
                source_kind=source_kind.value,
                title=title,
                final_url=final_url,
                content_type=content_type,
                sha256=sha256,
                status=status.value,
                error=error,
            )
            session.add(model)
            session.flush()
            return _to_source(model)

    # Atualiza os dados de identificação e estado da fonte.
    def update(
        self,
        source_id: int,
        *,
        title: str | None = None,
        final_url: str | None = None,
        content_type: str | None = None,
        sha256: str | None = None,
        source_kind: SourceKind | None = None,
        status: SourceStatus | None = None,
        error: str | None = None,
    ) -> Source:
        with session_scope(self.database_url) as session:
            model = session.get(SourceModel, source_id)
            if model is None:
                raise SourceNotFoundError(f"Fonte {source_id} não encontrada.")

            if title is not None:
                model.title = title
            if final_url is not None:
                model.final_url = final_url
            if content_type is not None:
                model.content_type = content_type
            if sha256 is not None:
                model.sha256 = sha256
            if source_kind is not None:
                model.source_kind = source_kind.value
            if status is not None:
                model.status = status.value
            if error is not None:
                model.error = error

            session.flush()
            return _to_source(model)

    # Atualiza apenas o estado da fonte.
    def update_status(
        self,
        source_id: int,
        status: SourceStatus,
        error: str | None = None,
    ) -> Source:
        with session_scope(self.database_url) as session:
            model = session.get(SourceModel, source_id)
            if model is None:
                raise SourceNotFoundError(f"Fonte {source_id} não encontrada.")

            model.status = status.value
            if error is not None:
                model.error = error
            session.flush()
            return _to_source(model)

    # Persiste o conteúdo extraído de uma fonte.
    def save_snapshot(
        self,
        source_id: int,
        *,
        raw_path: str,
        content_text: str,
        segments: list[dict[str, Any]],
        metadata: dict[str, Any],
        warnings: list[str],
        page_count: int,
        http_status: int | None,
    ) -> SourceSnapshot:
        with session_scope(self.database_url) as session:
            source = session.get(SourceModel, source_id)
            if source is None:
                raise SourceNotFoundError(f"Fonte {source_id} não encontrada.")

            model = SourceSnapshotModel(
                source_id=source_id,
                raw_path=raw_path,
                content_text=content_text,
                segments=segments,
                extra_metadata=metadata,
                warnings=warnings,
                page_count=page_count,
                http_status=http_status,
            )
            session.add(model)
            session.flush()
            return _to_snapshot(model)

    # Busca uma fonte pelo identificador.
    def get(self, source_id: int) -> Source:
        with session_scope(self.database_url) as session:
            model = session.get(SourceModel, source_id)
            if model is None:
                raise SourceNotFoundError(f"Fonte {source_id} não encontrada.")
            return _to_source(model)

    # Busca uma fonte com o snapshot extraído.
    def get_detail(self, source_id: int) -> SourceDetail:
        with session_scope(self.database_url) as session:
            model = session.get(SourceModel, source_id)
            if model is None:
                raise SourceNotFoundError(f"Fonte {source_id} não encontrada.")

            source = _to_source(model)
            snapshot = _to_snapshot(model.snapshot) if model.snapshot else None
            return SourceDetail(**source.model_dump(), snapshot=snapshot)

    # Lista a fonte e todos os seus descendentes (PDFs vinculados).
    def list_tree(self, source_id: int) -> list[Source]:
        with session_scope(self.database_url) as session:
            model = session.get(SourceModel, source_id)
            if model is None:
                raise SourceNotFoundError(f"Fonte {source_id} não encontrada.")

            items: list[Source] = []
            self._collect_tree(session, model, items)
            return items

    # Exclui uma fonte, seus descendentes, snapshot e trechos indexados.
    def delete(self, source_id: int) -> Source:
        with session_scope(self.database_url) as session:
            model = session.get(SourceModel, source_id)
            if model is None:
                raise SourceNotFoundError(f"Fonte {source_id} não encontrada.")

            deleted = _to_source(model)
            self._delete_tree(session, model)
            return deleted

    # Coleta recursivamente a fonte e seus descendentes.
    def _collect_tree(
        self,
        session: Session,
        model: SourceModel,
        items: list[Source],
    ) -> None:
        items.append(_to_source(model))
        children = session.scalars(
            select(SourceModel)
            .where(SourceModel.parent_source_id == model.id)
            .order_by(SourceModel.id)
        ).all()
        for child in children:
            self._collect_tree(session, child, items)

    # Remove recursivamente a fonte e seus descendentes.
    def _delete_tree(self, session: Session, model: SourceModel) -> None:
        children = session.scalars(
            select(SourceModel)
            .where(SourceModel.parent_source_id == model.id)
            .order_by(SourceModel.id)
        ).all()
        for child in children:
            self._delete_tree(session, child)
        session.delete(model)

    # Lista as fontes de um workspace.
    def list_by_workspace(self, workspace_id: int) -> list[Source]:
        with session_scope(self.database_url) as session:
            models = session.scalars(
                select(SourceModel)
                .where(SourceModel.workspace_id == workspace_id)
                .order_by(SourceModel.id)
            ).all()
            return [_to_source(model) for model in models]

    # Busca uma fonte já ingerida pelo hash do conteúdo.
    def find_by_hash(self, workspace_id: int, sha256: str) -> Source | None:
        with session_scope(self.database_url) as session:
            model = session.scalar(
                select(SourceModel)
                .where(SourceModel.workspace_id == workspace_id)
                .where(SourceModel.sha256 == sha256)
                .where(SourceModel.status.in_([SourceStatus.READY.value, SourceStatus.NEEDS_OCR.value]))
                .order_by(SourceModel.id)
                .limit(1)
            )
            return _to_source(model) if model is not None else None
