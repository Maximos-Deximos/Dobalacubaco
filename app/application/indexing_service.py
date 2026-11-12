# Casos de uso de chunking e indexação de fontes para o chat.

from __future__ import annotations

from app.ai.ollama_client import OllamaClient, OllamaError
from app.config import Settings, get_settings
from app.memory.chunk_repository import ChunkRepository
from app.memory.source_repository import SourceRepository
from app.memory.workspace_repository import WorkspaceRepository
from app.rag.chunker import Chunker
from app.schemas.rag import ChunkDraft, IndexResult
from app.schemas.source import SourceDetail, SourceStatus


# Erro lançado quando a indexação não pode ser concluída.
class IndexingError(RuntimeError):
    pass


# Orquestra chunking, geração de embeddings e persistência.
class IndexingService:
    def __init__(
        self,
        settings: Settings | None = None,
        workspace_repository: WorkspaceRepository | None = None,
        source_repository: SourceRepository | None = None,
        chunk_repository: ChunkRepository | None = None,
        embedder: OllamaClient | None = None,
        chunker: Chunker | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.workspace_repository = workspace_repository or WorkspaceRepository(
            self.settings.database_url
        )
        self.source_repository = source_repository or SourceRepository(
            self.settings.database_url
        )
        self.chunk_repository = chunk_repository or ChunkRepository(
            self.settings.database_url
        )
        self.embedder = embedder or OllamaClient(
            host=self.settings.ollama_host,
            timeout=self.settings.ollama_timeout,
        )
        self.chunker = chunker or Chunker(
            chunk_chars=self.settings.rag_chunk_chars,
            overlap=self.settings.rag_chunk_overlap,
        )

    # Indexa uma fonte específica ou todas as fontes do workspace.
    def index_workspace(
        self,
        workspace_id: int,
        *,
        source_id: int | None = None,
        force: bool = False,
    ) -> IndexResult:
        self.workspace_repository.get(workspace_id)
        result = IndexResult(
            workspace_id=workspace_id,
            embedding_model=self.settings.ollama_embed_model,
        )

        if source_id is not None:
            source = self.source_repository.get(source_id)
            if source.workspace_id != workspace_id:
                raise IndexingError(
                    f"A fonte {source_id} não pertence ao workspace {workspace_id}."
                )
            sources = [source]
        else:
            sources = self.source_repository.list_by_workspace(workspace_id)

        for source in sources:
            detail = self.source_repository.get_detail(source.id)
            if not self._can_index(detail, result):
                continue

            assert detail.snapshot is not None
            drafts = self.chunker.chunk(detail.snapshot)
            if not drafts:
                result.sources_skipped += 1
                result.warnings.append(
                    f"A fonte {source.id} não gerou trechos indexáveis."
                )
                continue

            existing = self.chunk_repository.list_by_source(source.id)
            if existing and not force and self._is_current(existing):
                result.sources_skipped += 1
                continue

            if existing:
                self.chunk_repository.delete_by_source(source.id)

            embeddings = self._generate_embeddings(drafts, result)
            self.chunk_repository.create_many(
                workspace_id=workspace_id,
                source_id=source.id,
                drafts=drafts,
                embeddings=embeddings,
                embedding_model=(
                    self.settings.ollama_embed_model if embeddings else None
                ),
            )

            result.sources_indexed += 1
            result.chunks_created += len(drafts)
            if embeddings:
                result.embeddings_created += len(embeddings)

        return result

    # Verifica se a fonte pode ser indexada.
    def _can_index(self, detail: SourceDetail, result: IndexResult) -> bool:
        if detail.status != SourceStatus.READY:
            result.sources_skipped += 1
            result.warnings.append(
                f"A fonte {detail.id} foi ignorada porque está com status "
                f"'{detail.status.value}'."
            )
            return False
        if detail.snapshot is None:
            result.sources_skipped += 1
            result.warnings.append(
                f"A fonte {detail.id} não possui snapshot extraído."
            )
            return False
        return True

    # Confere se os trechos existentes já usam o modelo configurado.
    def _is_current(self, chunks) -> bool:
        model = self.settings.ollama_embed_model
        return all(
            chunk.embedding is not None and chunk.embedding_model == model
            for chunk in chunks
        )

    # Gera embeddings em lotes; falhas não impedem a indexação lexical.
    def _generate_embeddings(
        self,
        drafts: list[ChunkDraft],
        result: IndexResult,
    ) -> list[list[float]] | None:
        model = self.settings.ollama_embed_model
        if not model:
            result.warnings.append(
                "Modelo de embedding não configurado; indexação apenas lexical."
            )
            return None

        texts = [draft.text for draft in drafts]
        embeddings: list[list[float]] = []
        batch_size = self.settings.rag_embed_batch

        try:
            for start in range(0, len(texts), batch_size):
                embeddings.extend(
                    self.embedder.embed(model, texts[start : start + batch_size])
                )
        except OllamaError as exc:
            result.warnings.append(
                f"Falha ao gerar embeddings com '{model}'; mantendo índice "
                f"lexical. {exc}"
            )
            return None

        if len(embeddings) != len(texts):
            result.warnings.append(
                "A quantidade de embeddings retornada foi inválida; mantendo "
                "índice lexical."
            )
            return None

        return embeddings
