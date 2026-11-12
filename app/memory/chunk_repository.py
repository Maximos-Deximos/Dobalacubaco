# Repositório dos trechos indexados e da busca lexical FTS5.

from __future__ import annotations

import re

from sqlalchemy import delete, func, select, text

from app.memory.database import session_scope
from app.memory.models import SourceChunkModel, SourceModel
from app.schemas.rag import ChunkDraft, SourceChunk, StoredChunk


# Extrai termos simples para montar uma consulta FTS5 segura.
def _query_tokens(query: str) -> list[str]:
    tokens = re.findall(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+", query.lower())
    return [token for token in tokens if len(token) > 1]


# Converte o modelo ORM no contrato Pydantic do trecho.
def _to_chunk(model: SourceChunkModel) -> SourceChunk:
    embedding = list(model.embedding) if model.embedding is not None else None
    return SourceChunk(
        id=model.id,
        workspace_id=model.workspace_id,
        source_id=model.source_id,
        chunk_index=model.chunk_index,
        text=model.text,
        char_start=model.char_start,
        char_end=model.char_end,
        page_number=model.page_number,
        section_title=model.section_title,
        chunk_hash=model.chunk_hash,
        embedding_model=model.embedding_model,
        embedding_dim=model.embedding_dim,
        embedding=embedding,
        indexed_at=model.indexed_at,
    )


# Repositório dos trechos de fontes e suas representações vetoriais.
class ChunkRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    # Remove todos os trechos de uma fonte.
    def delete_by_source(self, source_id: int) -> int:
        with session_scope(self.database_url) as session:
            result = session.execute(
                delete(SourceChunkModel).where(
                    SourceChunkModel.source_id == source_id
                )
            )
            return int(result.rowcount or 0)

    # Persiste os trechos de uma fonte com ou sem embeddings.
    def create_many(
        self,
        *,
        workspace_id: int,
        source_id: int,
        drafts: list[ChunkDraft],
        embeddings: list[list[float]] | None = None,
        embedding_model: str | None = None,
    ) -> list[SourceChunk]:
        if embeddings is not None and len(embeddings) != len(drafts):
            raise ValueError("A quantidade de embeddings difere dos trechos.")

        with session_scope(self.database_url) as session:
            models: list[SourceChunkModel] = []
            for index, draft in enumerate(drafts):
                embedding = embeddings[index] if embeddings is not None else None
                model = SourceChunkModel(
                    workspace_id=workspace_id,
                    source_id=source_id,
                    chunk_index=draft.chunk_index,
                    text=draft.text,
                    char_start=draft.char_start,
                    char_end=draft.char_end,
                    page_number=draft.page_number,
                    section_title=draft.section_title,
                    chunk_hash=draft.chunk_hash,
                    embedding=embedding,
                    embedding_model=embedding_model if embedding is not None else None,
                    embedding_dim=len(embedding) if embedding is not None else None,
                )
                session.add(model)
                models.append(model)

            session.flush()
            return [_to_chunk(model) for model in models]

    # Lista os trechos de uma fonte.
    def list_by_source(self, source_id: int) -> list[SourceChunk]:
        with session_scope(self.database_url) as session:
            models = session.scalars(
                select(SourceChunkModel)
                .where(SourceChunkModel.source_id == source_id)
                .order_by(SourceChunkModel.chunk_index)
            ).all()
            return [_to_chunk(model) for model in models]

    # Lista trechos do workspace, opcionalmente apenas com embeddings.
    def list_by_workspace(
        self,
        workspace_id: int,
        *,
        only_embedded: bool = False,
        embedding_model: str | None = None,
    ) -> list[StoredChunk]:
        statement = (
            select(SourceChunkModel, SourceModel)
            .join(SourceModel, SourceModel.id == SourceChunkModel.source_id)
            .where(SourceChunkModel.workspace_id == workspace_id)
            .order_by(SourceChunkModel.source_id, SourceChunkModel.chunk_index)
        )
        if only_embedded:
            statement = statement.where(SourceChunkModel.embedding_model.is_not(None))
        if embedding_model is not None:
            statement = statement.where(
                SourceChunkModel.embedding_model == embedding_model
            )

        with session_scope(self.database_url) as session:
            rows = session.execute(statement).all()
            return [
                StoredChunk(
                    chunk=_to_chunk(chunk),
                    source_title=source.title,
                    source_url=source.final_url or source.url,
                )
                for chunk, source in rows
            ]

    # Conta trechos totais e trechos com embeddings no workspace.
    def count_by_workspace(self, workspace_id: int) -> tuple[int, int]:
        with session_scope(self.database_url) as session:
            total = session.scalar(
                select(func.count(SourceChunkModel.id)).where(
                    SourceChunkModel.workspace_id == workspace_id
                )
            )
            embedded = session.scalar(
                select(func.count(SourceChunkModel.id))
                .where(SourceChunkModel.workspace_id == workspace_id)
                .where(SourceChunkModel.embedding_model.is_not(None))
            )
            return int(total or 0), int(embedded or 0)

    # Busca trechos usando o índice lexical FTS5 e BM25.
    def search_lexical(
        self,
        workspace_id: int,
        query: str,
        limit: int,
    ) -> list[StoredChunk]:
        tokens = _query_tokens(query)
        if not tokens:
            return []

        fts_query = " OR ".join(f'"{token}"' for token in tokens)
        statement = text(
            """
            SELECT
                c.id,
                c.workspace_id,
                c.source_id,
                c.chunk_index,
                c.text,
                c.char_start,
                c.char_end,
                c.page_number,
                c.section_title,
                c.chunk_hash,
                c.embedding_model,
                c.embedding_dim,
                c.indexed_at,
                s.title AS source_title,
                COALESCE(s.final_url, s.url) AS source_url,
                bm25(source_chunks_fts) AS rank
            FROM source_chunks_fts
            JOIN source_chunks c ON c.id = source_chunks_fts.rowid
            JOIN sources s ON s.id = c.source_id
            WHERE source_chunks_fts MATCH :query
              AND c.workspace_id = :workspace_id
            ORDER BY rank
            LIMIT :limit
            """
        )

        with session_scope(self.database_url) as session:
            rows = session.execute(
                statement,
                {
                    "query": fts_query,
                    "workspace_id": workspace_id,
                    "limit": limit,
                },
            ).mappings()
            results: list[StoredChunk] = []
            for row in rows:
                chunk = SourceChunk(
                    id=row["id"],
                    workspace_id=row["workspace_id"],
                    source_id=row["source_id"],
                    chunk_index=row["chunk_index"],
                    text=row["text"],
                    char_start=row["char_start"],
                    char_end=row["char_end"],
                    page_number=row["page_number"],
                    section_title=row["section_title"] or "",
                    chunk_hash=row["chunk_hash"],
                    embedding_model=row["embedding_model"],
                    embedding_dim=row["embedding_dim"],
                    embedding=None,
                    indexed_at=row["indexed_at"],
                )
                results.append(
                    StoredChunk(
                        chunk=chunk,
                        source_title=row["source_title"] or "",
                        source_url=row["source_url"],
                        score=-float(row["rank"]),
                    )
                )
            return results
