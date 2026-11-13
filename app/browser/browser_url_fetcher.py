# API local que liga o frontend à ingestão de URLs de editais.
#
# Expõe POST /get-url em http://localhost:8000. O endpoint reaproveita o mesmo
# SourceIngestionService usado pela CLI (source add) e pela TUI (aba Fontes),
# portanto herda as regras de segurança (UrlPolicy), os limites de tamanho e a
# persistência em SQLite. Nenhuma lógica de scraping é duplicada aqui.
#
# Execução (na raiz do projeto, com o ambiente virtual ativo):
#   python -m app.browser.browser_url_fetcher
# ou:
#   uvicorn app.browser.browser_url_fetcher:app --host 127.0.0.1 --port 8000

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from app.ai.provider import AiError
from app.application.indexing_service import IndexingError, IndexingService
from app.application.source_service import (
    IngestionResult,
    SourceIngestionError,
    SourceIngestionService,
)
from app.config import get_settings
from app.ingestion.fetcher import FetchError
from app.logging_config import configure_logging
from app.memory.database import init_db
from app.memory.workspace_repository import WorkspaceNotFoundError
from app.schemas.source import Source
from app.security.url_policy import UrlPolicyError

logger = logging.getLogger(__name__)

# O servidor só aceita conexões da própria máquina.
API_HOST = "127.0.0.1"
API_PORT = 8000

# Aceita o frontend em qualquer porta de localhost (Vite, Next, CRA, etc.).
LOCAL_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


# Dados enviados pelo frontend ao vincular uma URL.
class GetUrlRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    workspace_id: int = Field(ge=1)
    url: str = Field(min_length=1, max_length=2048)
    # Renderiza a página com Chromium (para sites que dependem de JavaScript).
    use_browser: bool = False
    # Ingere também os PDFs do mesmo domínio linkados na página.
    follow_pdfs: bool = False
    # Limite de PDFs vinculados; vazio usa MAX_LINKED_PDFS do .env.
    max_links: int | None = Field(default=None, ge=0)
    # Indexa as fontes ingeridas para que o chat possa consultá-las.
    index: bool = False


# Resumo da indexação quando solicitada.
class IndexSummary(BaseModel):
    sources_indexed: int = 0
    sources_skipped: int = 0
    chunks_created: int = 0
    embeddings_created: int = 0
    warnings: list[str] = Field(default_factory=list)


# Resposta devolvida ao frontend.
class GetUrlResponse(BaseModel):
    source: Source
    children: list[Source] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    duplicate: bool = False
    indexing: IndexSummary | None = None


# Serviços são criados uma vez e podem ser trocados em testes.
@lru_cache(maxsize=1)
def get_source_service() -> SourceIngestionService:
    return SourceIngestionService()


@lru_cache(maxsize=1)
def get_indexing_service() -> IndexingService:
    return IndexingService()


# Prepara logs e banco antes de atender requisições.
@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    init_db()
    yield


app = FastAPI(title="Agente de Editais - URLs", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=LOCAL_ORIGIN_REGEX,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)


# Indexa a fonte principal e os PDFs vinculados sem perder a ingestão se falhar.
def _index_sources(
    indexing: IndexingService,
    workspace_id: int,
    sources: list[Source],
) -> IndexSummary:
    summary = IndexSummary()

    for source in sources:
        try:
            result = indexing.index_workspace(workspace_id, source_id=source.id)
        except (IndexingError, AiError) as exc:
            summary.sources_skipped += 1
            summary.warnings.append(f"Falha ao indexar a fonte {source.id}: {exc}")
            continue

        summary.sources_indexed += result.sources_indexed
        summary.sources_skipped += result.sources_skipped
        summary.chunks_created += result.chunks_created
        summary.embeddings_created += result.embeddings_created
        summary.warnings.extend(result.warnings)

    return summary


# Monta a resposta HTTP a partir do resultado da ingestão.
def _build_response(
    result: IngestionResult,
    indexing: IndexSummary | None,
) -> GetUrlResponse:
    return GetUrlResponse(
        source=result.source,
        children=result.children,
        warnings=result.warnings,
        duplicate=result.duplicate,
        indexing=indexing,
    )


# Recebe uma URL do frontend e a ingere no workspace informado.
# A função é síncrona de propósito: o FastAPI a executa em uma thread, o que
# permite ao serviço usar asyncio.run (Playwright) sem conflito com o servidor.
@app.post("/get-url", response_model=GetUrlResponse)
def get_url(
    payload: GetUrlRequest,
    sources: SourceIngestionService = Depends(get_source_service),
    indexing: IndexingService = Depends(get_indexing_service),
) -> GetUrlResponse:
    try:
        result = sources.add_url(
            payload.workspace_id,
            payload.url,
            use_browser=payload.use_browser,
            follow_pdfs=payload.follow_pdfs,
            max_links=payload.max_links,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UrlPolicyError as exc:
        # URL recusada pela política de segurança (HTTPS, SSRF, domínios).
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FetchError as exc:
        # O site de origem falhou ou devolveu algo que não é HTML/PDF.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except SourceIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falha inesperada ao ingerir a URL.")
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao processar a URL.",
        ) from exc

    summary = None
    if payload.index:
        summary = _index_sources(
            indexing,
            payload.workspace_id,
            [result.source, *result.children],
        )

    return _build_response(result, summary)


# Sobe o servidor local.
def main() -> None:
    import uvicorn

    uvicorn.run(app, host=API_HOST, port=API_PORT)


if __name__ == "__main__":
    main()
