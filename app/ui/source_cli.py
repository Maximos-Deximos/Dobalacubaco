# Comandos de ingestão de fontes da interface de linha de comando.

from __future__ import annotations

import argparse
import json
import sys

from app.application.indexing_service import IndexingError, IndexingService
from app.application.source_service import (
    IngestionResult,
    SourceIngestionError,
    SourceIngestionService,
)
from app.ingestion.fetcher import FetchError
from app.memory.database import init_db
from app.memory.source_repository import SourceNotFoundError
from app.memory.workspace_repository import WorkspaceNotFoundError
from app.schemas.source import Source, SourceDetail
from app.security.url_policy import UrlPolicyError


# Adiciona uma URL pública ao workspace.
def command_source_add(args: argparse.Namespace) -> int:
    init_db()
    service = SourceIngestionService()

    try:
        result = service.add_url(
            args.workspace_id,
            args.url,
            use_browser=args.use_browser,
            follow_pdfs=args.follow_pdfs,
            max_links=args.max_links,
        )
    except (
        WorkspaceNotFoundError,
        UrlPolicyError,
        FetchError,
        SourceIngestionError,
    ) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    _print_ingestion_result(result)
    return 0


# Adiciona um arquivo HTML ou PDF ao workspace.
def command_source_add_file(args: argparse.Namespace) -> int:
    init_db()
    service = SourceIngestionService()

    try:
        result = service.add_file(args.workspace_id, args.path)
    except (WorkspaceNotFoundError, SourceIngestionError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    _print_ingestion_result(result)
    return 0


# Cria ou atualiza o índice de busca de um workspace.
def command_source_index(args: argparse.Namespace) -> int:
    init_db()
    service = IndexingService()

    try:
        result = service.index_workspace(
            args.workspace_id,
            source_id=args.source_id,
            force=args.force,
        )
    except (WorkspaceNotFoundError, SourceNotFoundError, IndexingError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(result.model_dump_json(indent=2))
        return 0

    print(
        f"Indexação concluída: {result.sources_indexed} fonte(s), "
        f"{result.chunks_created} trecho(s), "
        f"{result.embeddings_created} embedding(s)."
    )
    if result.sources_skipped:
        print(f"Fontes ignoradas: {result.sources_skipped}.")
    if result.warnings:
        print("Avisos:")
        for warning in result.warnings:
            print(f"  - {warning}")
    return 0


# Lista as fontes de um workspace.
def command_source_list(args: argparse.Namespace) -> int:
    init_db()
    service = SourceIngestionService()

    try:
        sources = service.list_sources(args.workspace_id)
    except WorkspaceNotFoundError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(
            json.dumps(
                [source.model_dump(mode="json") for source in sources],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not sources:
        print("Nenhuma fonte cadastrada neste workspace.")
        return 0

    for source in sources:
        title = source.title or "(sem título)"
        print(
            f"{source.id:<5} {source.source_kind.value:<14} "
            f"{source.status.value:<11} {title}"
        )
    return 0


# Exibe uma fonte com o snapshot extraído.
def command_source_show(args: argparse.Namespace) -> int:
    init_db()
    service = SourceIngestionService()

    try:
        detail = service.get_source(args.source_id)
    except SourceNotFoundError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(detail.model_dump_json(indent=2))
        return 0

    _print_source_detail(detail)
    return 0


# Imprime o resultado de uma ingestão.
def _print_ingestion_result(result: IngestionResult) -> None:
    if result.duplicate:
        print(
            f"Fonte já ingerida anteriormente (id={result.source.id}). "
            "Nenhum arquivo novo foi criado."
        )
    else:
        print(
            f"Fonte '{result.source.title or result.source.url or result.source.id}' "
            f"ingerida com status '{result.source.status.value}' "
            f"(id={result.source.id})."
        )

    if result.children:
        print("Documentos vinculados:")
        for child in result.children:
            print(f"  - {child.id}: {child.title or child.url}")

    if result.warnings:
        print("Avisos:")
        for warning in result.warnings:
            print(f"  - {warning}")


# Imprime os dados principais da fonte e do snapshot.
def _print_source_detail(detail: SourceDetail) -> None:
    source: Source = detail
    print(f"ID: {source.id}")
    print(f"Workspace: {source.workspace_id}")
    print(f"Tipo: {source.source_kind.value}")
    print(f"Status: {source.status.value}")
    print(f"Título: {source.title or '(sem título)'}")
    print(f"URL: {source.url or '(arquivo local)'}")
    print(f"URL final: {source.final_url or '(não informada)'}")
    print(f"Content-Type: {source.content_type or '(não informado)'}")
    print(f"SHA-256: {source.sha256 or '(não informado)'}")

    if source.error:
        print(f"Erro: {source.error}")

    snapshot = detail.snapshot
    if snapshot is None:
        print("Snapshot: não disponível.")
        return

    print(f"Arquivo original: {snapshot.raw_path}")
    print(f"Páginas: {snapshot.page_count}")
    print(f"Segmentos: {len(snapshot.segments)}")
    print(f"Caracteres: {len(snapshot.content_text)}")

    if snapshot.warnings:
        print("Avisos:")
        for warning in snapshot.warnings:
            print(f"  - {warning}")

    print("\nPrévia:")
    preview = snapshot.content_text[:1000]
    print(preview or "(sem texto extraído)")
    if len(snapshot.content_text) > len(preview):
        print("...")
