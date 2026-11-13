# Casos de uso do preenchimento assistido de formulários PDF.

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

from app.ai.ollama_client import OllamaClient, OllamaError
from app.ai.promts import (
    NO_INDEXED_SOURCES_WARNING,
    NO_RELEVANT_EXCERPTS_WARNING,
    build_pdf_suggestion_messages,
)
from app.ai.response_parser import PdfSuggestionParseError, parse_pdf_suggestions
from app.config import Settings, get_settings
from app.ingestion.pdf_form import PdfFormError, PdfFormFiller, PdfFormInspector
from app.memory.chunk_repository import ChunkRepository
from app.memory.pdf_form_repository import (
    PdfFormRepository,
    PdfMemoryRepository,
    normalize_text,
)
from app.memory.source_repository import SourceRepository
from app.memory.user_repository import UserRepository
from app.rag.pdf_memory_index import PdfMemoryIndex
from app.rag.retriever import Retriever
from app.schemas.pdf import (
    PdfFieldMemory,
    PdfFieldRecord,
    PdfFieldStatus,
    PdfFieldType,
    PdfFillResult,
    PdfFormInspection,
    PdfFormSessionDetail,
    PdfGenerationStatus,
    PdfSessionStatus,
    PdfSuggestionBatch,
    PdfSuggestionSource,
)
from app.schemas.profile import UserProfile
from app.schemas.source import SourceDetail, SourceKind


# Erro de regra de negócio do preenchimento de PDF.
class PdfFormServiceError(RuntimeError):
    pass


# Tamanho dos lotes enviados ao modelo.
PDF_AI_BATCH_SIZE = 4

PDF_SOURCE_KINDS = {SourceKind.WEB_PDF, SourceKind.UPLOADED_PDF}

# Padrões de rótulos comuns mapeados para o perfil local.
PROFILE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("full_name", ("nome completo", "nome do responsavel", "nome do candidato", "full name")),
    ("first_name", ("primeiro nome", "first name")),
    ("last_name", ("sobrenome", "last name")),
    ("email", ("e-mail", "email", "correio eletronico")),
    ("phone", ("telefone", "celular", "fone", "phone", "whatsapp")),
    ("organization", ("organizacao", "empresa", "instituicao", "organization")),
    ("role", ("cargo", "funcao", "role")),
    ("address", ("endereco", "address")),
    ("city", ("cidade", "city", "municipio")),
    ("state", ("estado", "uf", "state")),
    ("postal_code", ("cep", "codigo postal", "postal code", "zip")),
    ("country", ("pais", "country")),
    ("birth_date", ("nascimento", "birth")),
)


# Orquestra inspeção, sugestões vetoriais, revisão e gravação do PDF.
class PdfFormService:
    def __init__(
        self,
        settings: Settings | None = None,
        source_repository: SourceRepository | None = None,
        form_repository: PdfFormRepository | None = None,
        memory_repository: PdfMemoryRepository | None = None,
        user_repository: UserRepository | None = None,
        chunk_repository: ChunkRepository | None = None,
        retriever: Retriever | None = None,
        client: OllamaClient | None = None,
        memory_index: PdfMemoryIndex | None = None,
        inspector: PdfFormInspector | None = None,
        filler: PdfFormFiller | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.source_repository = source_repository or SourceRepository(
            self.settings.database_url
        )
        self.form_repository = form_repository or PdfFormRepository(
            self.settings.database_url
        )
        self.memory_repository = memory_repository or PdfMemoryRepository(
            self.settings.database_url
        )
        self.user_repository = user_repository or UserRepository(
            self.settings.database_url
        )
        self.chunk_repository = chunk_repository or ChunkRepository(
            self.settings.database_url
        )
        self.client = client or OllamaClient(
            host=self.settings.ollama_host,
            timeout=self.settings.ollama_timeout,
        )
        self.retriever = retriever or Retriever(
            settings=self.settings,
            chunk_repository=self.chunk_repository,
            embedder=self.client,
        )
        self.memory_index = memory_index or PdfMemoryIndex(
            settings=self.settings,
            repository=self.memory_repository,
        )
        self.inspector = inspector or PdfFormInspector()
        self.filler = filler or PdfFormFiller()

    # Inspeciona os campos AcroForm de uma fonte já ingerida.
    def inspect_source(self, source_id: int) -> PdfFormInspection:
        detail = self._pdf_source(source_id)
        content = self._read_source(detail)
        try:
            inspected = self.inspector.inspect(content)
        except PdfFormError as exc:
            raise PdfFormServiceError(str(exc)) from exc

        return PdfFormInspection(
            source_id=detail.id,
            workspace_id=detail.workspace_id,
            source_title=detail.title,
            raw_path=detail.snapshot.raw_path if detail.snapshot else "",
            page_count=inspected.page_count,
            fields=inspected.fields,
            warnings=inspected.warnings,
        )

    # Abre a sessão mais recente ou cria uma nova para a fonte.
    def open_session(
        self,
        source_id: int,
        *,
        instructions: str = "",
        force_new: bool = False,
    ) -> PdfFormSessionDetail:
        if not force_new:
            existing = self.form_repository.find_latest_open(source_id)
            if existing is not None:
                if instructions and not existing.instructions:
                    return self.form_repository.update_session(
                        existing.id, instructions=instructions
                    )
                return existing

        inspection = self.inspect_source(source_id)
        return self.form_repository.create_session(
            workspace_id=inspection.workspace_id,
            source_id=inspection.source_id,
            instructions=instructions,
            fields=inspection.fields,
        )

    # Devolve a sessão persistida com seus campos.
    def get_session(self, session_id: int) -> PdfFormSessionDetail:
        return self.form_repository.get_session(session_id)

    # Gera sugestões progressivamente, emitindo lotes para a TUI.
    def suggest_live(
        self,
        session_id: int,
        *,
        refresh: bool = False,
    ) -> Iterator[PdfSuggestionBatch]:
        session = self.form_repository.get_session(session_id)
        existing_suggestions = any(
            field.suggested_value is not None for field in session.fields
        )
        if existing_suggestions and not refresh:
            yield PdfSuggestionBatch(
                session_id=session_id,
                fields=session.fields,
                completed=len(
                    [
                        field
                        for field in session.fields
                        if field.status != PdfFieldStatus.PENDING
                    ]
                ),
                total=len(session.fields),
                done=True,
                generation_status=PdfGenerationStatus.COMPLETED,
                warnings=["Sugestões já existentes; use --refresh para gerar novamente."],
            )
            return

        if refresh:
            session = self._reset_manual_preserving(session)

        total = len(session.fields)
        self.form_repository.update_session(
            session_id,
            generation_status=PdfGenerationStatus.RUNNING,
            generation_progress=0,
            generation_total=total,
            error=None,
            status=PdfSessionStatus.REVIEWING,
        )

        warnings: list[str] = []
        profile = self.user_repository.get_default()
        fields = session.fields
        profile_updates = self._profile_suggestions(fields, profile)
        vector_updates, vector_warnings = self._vector_suggestions(
            session.workspace_id,
            fields,
            session.instructions,
        )
        warnings.extend(vector_warnings)

        updated: dict[str, PdfFieldRecord] = {}
        for suggestion in profile_updates + vector_updates:
            record = self._apply_suggestion(
                session_id,
                suggestion["field_name"],
                suggestion["value"],
                suggestion["confidence"],
                suggestion["rationale"],
                suggestion["source"],
            )
            if record is not None:
                updated[record.field_name] = record

        current = self.form_repository.get_session(session_id)
        completed = self._completed_count(current.fields)
        self.form_repository.update_session(
            session_id,
            generation_progress=completed,
        )
        if updated:
            yield PdfSuggestionBatch(
                session_id=session_id,
                fields=list(updated.values()),
                completed=completed,
                total=total,
                generation_status=PdfGenerationStatus.RUNNING,
                warnings=list(warnings),
            )

        unresolved = [
            field
            for field in current.fields
            if field.suggested_value is None
            and not field.readonly
            and field.field_type not in {PdfFieldType.SIGNATURE, PdfFieldType.UNKNOWN}
        ]
        if not unresolved:
            self._finish_generation(session_id, total, warnings)
            yield PdfSuggestionBatch(
                session_id=session_id,
                fields=self.form_repository.get_session(session_id).fields,
                completed=total,
                total=total,
                done=True,
                generation_status=PdfGenerationStatus.COMPLETED,
                warnings=warnings,
            )
            return

        contexts, memories, context_warnings = self._retrieval_contexts(
            session.workspace_id,
            unresolved,
            profile,
            session.instructions,
        )
        warnings.extend(context_warnings)

        for start in range(0, len(unresolved), PDF_AI_BATCH_SIZE):
            batch = unresolved[start : start + PDF_AI_BATCH_SIZE]
            try:
                messages = build_pdf_suggestion_messages(
                    batch,
                    profile.model_dump(mode="json", exclude_none=True) if profile else {},
                    contexts=contexts,
                    memories=memories,
                    instructions=session.instructions,
                    max_context_chars=self.settings.rag_max_context_chars,
                )
                raw = self.client.chat(
                    self.settings.ollama_model,
                    messages,
                    temperature=self.settings.rag_temperature,
                )
                suggestions, parse_warnings = parse_pdf_suggestions(raw, batch)
                warnings.extend(parse_warnings)
            except (OllamaError, PdfSuggestionParseError) as exc:
                warnings.append(f"Falha ao gerar sugestões com a IA: {exc}")
                break
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Erro inesperado ao gerar sugestões: {exc}")
                break

            updated = {}
            for suggestion in suggestions:
                record = self._apply_suggestion(
                    session_id,
                    suggestion.field_name,
                    suggestion.value,
                    suggestion.confidence,
                    suggestion.rationale,
                    PdfSuggestionSource.AI,
                )
                if record is not None:
                    updated[record.field_name] = record

            current = self.form_repository.get_session(session_id)
            completed = self._completed_count(current.fields)
            self.form_repository.update_session(
                session_id,
                generation_progress=completed,
            )
            if updated:
                yield PdfSuggestionBatch(
                    session_id=session_id,
                    fields=list(updated.values()),
                    completed=completed,
                    total=total,
                    generation_status=PdfGenerationStatus.RUNNING,
                    warnings=list(warnings),
                )

        self._finish_generation(session_id, total, warnings)
        final = self.form_repository.get_session(session_id)
        yield PdfSuggestionBatch(
            session_id=session_id,
            fields=final.fields,
            completed=total,
            total=total,
            done=True,
            generation_status=PdfGenerationStatus.COMPLETED,
            warnings=warnings,
        )

    # Atualiza um valor editado manualmente com validação e autosave.
    def update_field_live(
        self,
        session_id: int,
        field_name: str,
        value: str | None,
    ) -> PdfFieldRecord:
        field = self.form_repository.get_field(session_id, field_name)
        self._validate_value(field, value)
        normalized = None if value is None or not str(value).strip() else str(value).strip()
        updated = self.form_repository.update_field(
            session_id,
            field_name,
            final_value=normalized,
            status=PdfFieldStatus.EDITED,
            suggestion_source=PdfSuggestionSource.MANUAL,
            increment_revision=True,
        )
        if updated is None:
            raise PdfFormServiceError(
                "O campo foi alterado por outra operação; recarregue a sessão."
            )
        self.form_repository.update_session(
            session_id,
            status=PdfSessionStatus.REVIEWING,
        )
        return updated

    # Aprova um campo, usando a sugestão quando necessário.
    def approve_field(self, session_id: int, field_name: str) -> PdfFieldRecord:
        field = self.form_repository.get_field(session_id, field_name)
        if field.readonly or field.field_type == PdfFieldType.SIGNATURE:
            raise PdfFormServiceError("Este campo não pode ser aprovado.")
        value = field.final_value if field.final_value is not None else field.suggested_value
        self._validate_value(field, value)
        if value is None:
            raise PdfFormServiceError("O campo não possui valor para aprovar.")

        updated = self.form_repository.update_field(
            session_id,
            field_name,
            final_value=value,
            status=PdfFieldStatus.APPROVED,
            increment_revision=True,
        )
        if updated is None:
            raise PdfFormServiceError("Não foi possível aprovar o campo.")
        self.form_repository.update_session(
            session_id,
            status=PdfSessionStatus.READY,
        )
        return updated

    # Aprova todos os campos que possuem sugestão ou valor final.
    def approve_all(self, session_id: int) -> PdfFormSessionDetail:
        session = self.form_repository.get_session(session_id)
        for field in session.fields:
            if field.readonly or field.field_type == PdfFieldType.SIGNATURE:
                continue
            value = field.final_value if field.final_value is not None else field.suggested_value
            if value is None:
                continue
            self._validate_value(field, value)
            self.form_repository.update_field(
                session_id,
                field.field_name,
                final_value=value,
                status=PdfFieldStatus.APPROVED,
                increment_revision=True,
            )
        self.form_repository.update_session(
            session_id,
            status=PdfSessionStatus.READY,
        )
        return self.form_repository.get_session(session_id)

    # Preenche o PDF, grava uma nova cópia e alimenta a memória vetorial.
    def fill(
        self,
        session_id: int,
        output_path: str | Path,
        *,
        flatten: bool = False,
        overrides: dict[str, str | None] | None = None,
    ) -> PdfFillResult:
        session = self.form_repository.get_session(session_id)
        source = self._pdf_source(session.source_id)
        raw_path = Path(source.snapshot.raw_path).expanduser().resolve() if source.snapshot else None
        if raw_path is None:
            raise PdfFormServiceError("A fonte não possui arquivo original.")

        fields = {field.field_name: field for field in session.fields}
        if overrides:
            for field_name, value in overrides.items():
                field = fields.get(field_name)
                if field is None:
                    raise PdfFormServiceError(
                        f"Campo '{field_name}' não pertence à sessão {session_id}."
                    )
                self._validate_value(field, value)
                self.form_repository.update_field(
                    session_id,
                    field_name,
                    final_value=value,
                    status=PdfFieldStatus.APPROVED,
                    suggestion_source=PdfSuggestionSource.MANUAL,
                    increment_revision=True,
                )
            session = self.form_repository.get_session(session_id)
            fields = {field.field_name: field for field in session.fields}

        values: dict[str, str] = {}
        for field in fields.values():
            if field.status not in {
                PdfFieldStatus.APPROVED,
                PdfFieldStatus.EDITED,
                PdfFieldStatus.FILLED,
            }:
                continue
            if field.final_value is None:
                continue
            if field.readonly or field.field_type == PdfFieldType.SIGNATURE:
                continue
            values[field.field_name] = field.final_value

        if not values:
            raise PdfFormServiceError(
                "Nenhum campo aprovado ou editado para preencher."
            )

        destination = Path(output_path).expanduser().resolve()
        if destination == raw_path:
            raise PdfFormServiceError(
                "O arquivo de saída não pode ser o PDF original."
            )
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            content = raw_path.read_bytes()
            filled = self.filler.fill(content, values, flatten=flatten)
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_bytes(filled)
            temporary.replace(destination)
        except (OSError, PdfFormError) as exc:
            self.form_repository.update_session(
                session_id,
                status=PdfSessionStatus.FAILED,
                error=str(exc),
            )
            raise PdfFormServiceError(f"Falha ao gravar o PDF: {exc}") from exc

        self.form_repository.mark_filled(
            session_id,
            output_path=str(destination),
            field_names=list(values),
        )
        warnings = self._save_memories(
            workspace_id=session.workspace_id,
            source_id=session.source_id,
            fields=[fields[name] for name in values],
        )
        self.form_repository.update_session(session_id, status=PdfSessionStatus.FILLED)

        return PdfFillResult(
            session_id=session_id,
            output_path=str(destination),
            fields_filled=len(values),
            fields_skipped=len(fields) - len(values),
            warnings=warnings,
        )

    # Aplica uma sugestão respeitando a revisão e edições manuais.
    def _apply_suggestion(
        self,
        session_id: int,
        field_name: str,
        value: str | None,
        confidence: float,
        rationale: str,
        source: PdfSuggestionSource,
    ) -> PdfFieldRecord | None:
        field = self.form_repository.get_field(session_id, field_name)
        if field.status in {
            PdfFieldStatus.EDITED,
            PdfFieldStatus.APPROVED,
            PdfFieldStatus.FILLED,
        }:
            return None
        if field.readonly or field.field_type == PdfFieldType.SIGNATURE:
            return None
        try:
            self._validate_value(field, value)
        except PdfFormServiceError:
            return None

        return self.form_repository.update_field(
            session_id,
            field_name,
            expected_revision=field.revision,
            suggested_value=value,
            final_value=value,
            confidence=confidence,
            rationale=rationale,
            suggestion_source=source,
            status=PdfFieldStatus.SUGGESTED,
            warnings=field.warnings,
        )

    # Gera sugestões determinísticas a partir do perfil local.
    def _profile_suggestions(
        self,
        fields: list[PdfFieldRecord],
        profile: UserProfile | None,
    ) -> list[dict]:
        if profile is None:
            return []

        custom = {
            normalize_text(key): value
            for key, value in (profile.custom_answers or {}).items()
        }
        suggestions: list[dict] = []

        for field in fields:
            if field.readonly or field.field_type in {
                PdfFieldType.SIGNATURE,
                PdfFieldType.UNKNOWN,
            }:
                continue
            label_key = normalize_text(f"{field.label} {field.field_name}")

            value = None
            rationale = ""
            for key, custom_value in custom.items():
                if key and (key == label_key or key in label_key):
                    value = custom_value
                    rationale = "Resposta personalizada cadastrada no perfil."
                    break

            if value is None:
                for profile_key, patterns in PROFILE_PATTERNS:
                    if not any(pattern in label_key for pattern in patterns):
                        continue
                    raw = getattr(profile, profile_key, None)
                    if raw is None or raw == "":
                        continue
                    value = raw.isoformat() if isinstance(raw, date) else str(raw)
                    rationale = f"Dado encontrado no perfil local ({profile_key})."
                    break

            if value is None or not self._value_allowed(field, value):
                continue
            suggestions.append(
                {
                    "field_name": field.field_name,
                    "value": value,
                    "confidence": 0.92,
                    "rationale": rationale,
                    "source": PdfSuggestionSource.PROFILE,
                }
            )
        return suggestions

    # Gera sugestões iniciais a partir da memória vetorial do workspace.
    def _vector_suggestions(
        self,
        workspace_id: int,
        fields: list[PdfFieldRecord],
        instructions: str,
    ) -> tuple[list[dict], list[str]]:
        warnings: list[str] = []
        model = self.settings.ollama_embed_model
        if not model:
            return [], ["Modelo de embedding não configurado; memória vetorial ignorada."]

        candidates = [
            field
            for field in fields
            if not field.readonly
            and field.field_type not in {PdfFieldType.SIGNATURE, PdfFieldType.UNKNOWN}
        ]
        if not candidates:
            return [], []

        texts = [self._field_query(field, instructions) for field in candidates]
        try:
            embeddings = self.client.embed(model, texts)
        except OllamaError as exc:
            return [], [f"Memória vetorial indisponível: {exc}"]

        matches = self.memory_index.similar_many(
            workspace_id,
            embeddings,
            embedding_model=model,
            top_k=3,
            min_score=0.82,
        )
        suggestions: list[dict] = []
        for field, field_matches in zip(candidates, matches, strict=False):
            for match in field_matches:
                memory = match.item
                if not self._memory_compatible(field, memory):
                    continue
                if match.score < 0.90 or not self._value_allowed(field, memory.value):
                    continue
                suggestions.append(
                    {
                        "field_name": field.field_name,
                        "value": memory.value,
                        "confidence": round(match.score, 4),
                        "rationale": (
                            "Valor semelhante já revisado e aprovado neste workspace."
                        ),
                        "source": PdfSuggestionSource.VECTOR,
                    }
                )
                break
        return suggestions, warnings

    # Recupera contexto do edital e exemplos da memória para o prompt.
    def _retrieval_contexts(
        self,
        workspace_id: int,
        fields: list[PdfFieldRecord],
        profile: UserProfile | None,
        instructions: str,
    ) -> tuple[
        dict[str, list],
        dict[str, list[tuple[PdfFieldMemory, float]]],
        list[str],
    ]:
        warnings: list[str] = []
        contexts: dict[str, list] = {field.field_name: [] for field in fields}
        memories: dict[str, list[tuple[PdfFieldMemory, float]]] = {
            field.field_name: [] for field in fields
        }

        model = self.settings.ollama_embed_model
        if model:
            texts = [self._field_query(field, instructions) for field in fields]
            try:
                embeddings = self.client.embed(model, texts)
                matches = self.memory_index.similar_many(
                    workspace_id,
                    embeddings,
                    embedding_model=model,
                    top_k=3,
                    min_score=0.70,
                )
                for field, field_matches in zip(fields, matches, strict=False):
                    memories[field.field_name] = [
                        (match.item, match.score)
                        for match in field_matches
                        if self._memory_compatible(field, match.item)
                    ]
            except OllamaError as exc:
                warnings.append(f"Memória vetorial indisponível: {exc}")

        chunks_total, _ = self.chunk_repository.count_by_workspace(workspace_id)
        if chunks_total == 0:
            warnings.append(NO_INDEXED_SOURCES_WARNING)
            return contexts, memories, warnings

        queries = [self._field_query(field, instructions) for field in fields]
        try:
            results = self.retriever.retrieve_many(workspace_id, queries)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Falha na busca vetorial do edital: {exc}")
            return contexts, memories, warnings

        for field, result in zip(fields, results, strict=False):
            contexts[field.field_name] = result.hits
            warnings.extend(result.warnings)
            if not result.hits:
                warnings.append(NO_RELEVANT_EXCERPTS_WARNING)

        return contexts, memories, _dedupe(warnings)

    # Remove sugestões de campos editados manualmente ao regenerar.
    def _reset_manual_preserving(
        self,
        session: PdfFormSessionDetail,
    ) -> PdfFormSessionDetail:
        for field in session.fields:
            if field.status in {
                PdfFieldStatus.EDITED,
                PdfFieldStatus.APPROVED,
                PdfFieldStatus.FILLED,
            }:
                continue
            self.form_repository.update_field(
                session.id,
                field.field_name,
                suggested_value=None,
                final_value=None,
                confidence=None,
                rationale="",
                suggestion_source=None,
                status=PdfFieldStatus.PENDING,
                expected_revision=field.revision,
            )
        return self.form_repository.get_session(session.id)

    # Finaliza o estado de geração.
    def _finish_generation(
        self,
        session_id: int,
        total: int,
        warnings: list[str],
    ) -> None:
        self.form_repository.update_session(
            session_id,
            generation_status=PdfGenerationStatus.COMPLETED,
            generation_progress=total,
            generation_total=total,
            status=PdfSessionStatus.SUGGESTED,
            last_suggested_at=datetime.now(UTC),
            error=None,
        )

    # Salva valores aprovados na memória vetorial.
    def _save_memories(
        self,
        *,
        workspace_id: int,
        source_id: int,
        fields: list[PdfFieldRecord],
    ) -> list[str]:
        warnings: list[str] = []
        model = self.settings.ollama_embed_model
        texts = [self._memory_text(field, field.final_value or "") for field in fields]
        embeddings: list[list[float] | None] = [None] * len(fields)

        if model and texts:
            try:
                generated = self.client.embed(model, texts)
                if len(generated) == len(texts):
                    embeddings = list(generated)
                else:
                    warnings.append(
                        "A quantidade de embeddings de memória foi inválida; "
                        "valores salvos sem vetor."
                    )
            except OllamaError as exc:
                warnings.append(
                    f"Falha ao gerar embeddings da memória; valores salvos sem vetor. {exc}"
                )

        for field, text, embedding in zip(fields, texts, embeddings, strict=False):
            value = field.final_value
            if not value:
                continue
            try:
                self.memory_repository.upsert(
                    workspace_id=workspace_id,
                    source_id=source_id,
                    label=field.label or field.field_name,
                    field_name=field.field_name,
                    field_type=field.field_type.value,
                    value=value,
                    embedding=embedding,
                    embedding_model=model if embedding else None,
                )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Falha ao salvar memória do campo '{field.field_name}': {exc}")

        self.memory_index.invalidate(workspace_id)
        return warnings

    # Valida um valor contra o tipo, opções e tamanho do campo.
    def _validate_value(self, field: PdfFieldRecord, value: str | None) -> None:
        if field.readonly:
            raise PdfFormServiceError("Campo somente leitura.")
        if field.field_type == PdfFieldType.SIGNATURE:
            raise PdfFormServiceError("Campos de assinatura não são suportados.")
        if value is None:
            return
        text = str(value)
        if field.max_length is not None and len(text) > field.max_length:
            raise PdfFormServiceError(
                f"O campo '{field.label or field.field_name}' aceita no máximo "
                f"{field.max_length} caracteres."
            )
        choice_types = {
            PdfFieldType.CHOICE,
            PdfFieldType.RADIO,
            PdfFieldType.CHECKBOX,
        }
        if (
            field.field_type in choice_types
            and text
            and not self._value_allowed(field, text)
        ):
            allowed = ", ".join(option.value for option in field.options)
            raise PdfFormServiceError(
                f"Valor inválido para '{field.label or field.field_name}'. "
                f"Use um de: {allowed or 'Off'}."
            )

    # Confere se o valor pertence às opções do campo.
    def _value_allowed(self, field: PdfFieldRecord, value: str) -> bool:
        if field.field_type not in {
            PdfFieldType.CHOICE,
            PdfFieldType.RADIO,
            PdfFieldType.CHECKBOX,
        }:
            return True
        allowed = {option.value for option in field.options}
        return not allowed or value in allowed or value == "Off"

    # Confere compatibilidade entre campo atual e memória vetorial.
    def _memory_compatible(self, field: PdfFieldRecord, memory: PdfFieldMemory) -> bool:
        return field.field_type == memory.field_type

    # Monta o texto usado nas consultas vetoriais.
    def _field_query(self, field: PdfFieldRecord, instructions: str) -> str:
        options = " ".join(
            f"{option.label} {option.value}" for option in field.options
        )
        return " ".join(
            part
            for part in [
                field.label,
                field.field_name,
                field.field_type.value,
                options,
                instructions,
            ]
            if part
        ).strip()

    # Monta o texto vetorizado de uma memória.
    def _memory_text(self, field: PdfFieldRecord, value: str) -> str:
        return " | ".join(
            [
                field.label or field.field_name,
                field.field_name,
                field.field_type.value,
                value,
            ]
        )

    # Conta campos já processados.
    def _completed_count(self, fields: list[PdfFieldRecord]) -> int:
        return len(
            [field for field in fields if field.status != PdfFieldStatus.PENDING]
        )

    # Busca e valida a fonte PDF.
    def _pdf_source(self, source_id: int) -> SourceDetail:
        detail = self.source_repository.get_detail(source_id)
        if detail.source_kind not in PDF_SOURCE_KINDS:
            raise PdfFormServiceError(
                f"A fonte {source_id} não é um PDF."
            )
        if detail.snapshot is None or not detail.snapshot.raw_path:
            raise PdfFormServiceError(
                f"A fonte {source_id} não possui arquivo original disponível."
            )
        return detail

    # Lê o conteúdo binário do PDF.
    def _read_source(self, detail: SourceDetail) -> bytes:
        if detail.snapshot is None:
            raise PdfFormServiceError("A fonte não possui snapshot.")
        path = Path(detail.snapshot.raw_path).expanduser()
        try:
            return path.read_bytes()
        except OSError as exc:
            raise PdfFormServiceError(
                f"Não foi possível ler o PDF '{path}': {exc}"
            ) from exc


# Remove avisos duplicados preservando a ordem.
def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result

