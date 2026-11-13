# Modelos de dados da indexação e do chat com fontes locais.

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# Estratégia usada para recuperar trechos relevantes.
class RetrievalMode(str, Enum):
    SEMANTIC = "semantic"
    LEXICAL = "lexical"


# Trecho pronto para ser persistido após o chunking.
class ChunkDraft(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    page_number: int | None = None
    section_title: str = ""
    chunk_hash: str


# Trecho indexado de uma fonte.
class SourceChunk(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int
    workspace_id: int
    source_id: int
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    page_number: int | None = None
    section_title: str = ""
    chunk_hash: str
    embedding_model: str | None = None
    embedding_dim: int | None = None
    embedding: list[float] | None = Field(default=None, exclude=True)
    indexed_at: datetime


# Trecho acompanhado dos dados de citação da fonte.
class StoredChunk(BaseModel):
    chunk: SourceChunk
    source_title: str = ""
    source_url: str | None = None
    score: float = 0.0


# Trecho recuperado com pontuação de relevância.
class RetrievalHit(BaseModel):
    chunk: SourceChunk
    source_title: str = ""
    source_url: str | None = None
    score: float = 0.0
    mode: RetrievalMode = RetrievalMode.SEMANTIC


# Fonte citada em uma resposta.
class Citation(BaseModel):
    marker: str
    chunk_id: int
    source_id: int
    source_title: str = ""
    source_url: str | None = None
    page_number: int | None = None
    section_title: str = ""
    snippet: str = ""


# Mensagem do histórico do chat.
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


# Mensagem de conversa persistida no banco.
class ChatMessageRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    role: Literal["user", "assistant"]
    content: str
    extra_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# Resposta do agente com as fontes utilizadas.
class ChatAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    mode: RetrievalMode | None = None
    model: str = ""
    retrieved_count: int = 0
    warnings: list[str] = Field(default_factory=list)


# Reconstrói a resposta exibida a partir de uma mensagem persistida.
def answer_from_record(record: ChatMessageRecord) -> ChatAnswer | None:
    if record.role != "assistant":
        return None

    payload = record.extra_metadata.get("answer")
    if not isinstance(payload, dict):
        return None

    try:
        return ChatAnswer.model_validate(payload)
    except ValueError:
        return None


# Resultado da indexação de uma fonte ou workspace.
class IndexResult(BaseModel):
    workspace_id: int
    sources_indexed: int = 0
    sources_skipped: int = 0
    chunks_created: int = 0
    embeddings_created: int = 0
    embedding_model: str | None = None
    warnings: list[str] = Field(default_factory=list)


# Situação do índice de um workspace.
class ChatStatus(BaseModel):
    workspace_id: int
    sources_total: int = 0
    sources_ready: int = 0
    chunks_total: int = 0
    chunks_embedded: int = 0
    embedding_model: str | None = None
