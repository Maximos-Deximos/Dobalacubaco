# Comandos de chat e consulta ao índice local.

from __future__ import annotations

import argparse
import sys

from app.ai.provider import AiError
from app.application.chat_service import ChatService, ChatServiceError
from app.memory.database import init_db
from app.memory.workspace_repository import WorkspaceNotFoundError
from app.schemas.rag import ChatAnswer, ChatStatus, answer_from_record


# Executa uma pergunta única ao workspace.
def command_chat_ask(args: argparse.Namespace) -> int:
    init_db()
    service = ChatService()

    try:
        answer = service.ask(
            args.workspace_id,
            args.question,
            top_k=args.top_k,
        )
    except (WorkspaceNotFoundError, ChatServiceError, AiError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(answer.model_dump_json(indent=2))
        return 0

    _print_answer(answer)
    return 0


# Exibe a situação do índice do workspace.
def command_chat_status(args: argparse.Namespace) -> int:
    init_db()
    service = ChatService()

    try:
        status = service.status(args.workspace_id)
    except WorkspaceNotFoundError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(status.model_dump_json(indent=2))
        return 0

    _print_status(status)
    return 0


# Mantém uma conversa interativa no terminal.
def command_chat_repl(args: argparse.Namespace) -> int:
    init_db()
    service = ChatService()

    try:
        service.status(args.workspace_id)
        saved = len(service.conversation(args.workspace_id))
    except WorkspaceNotFoundError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    print("Chat local iniciado. Use /help para ver os comandos e /exit para sair.")
    if saved:
        print(
            f"Histórico restaurado: {saved} mensagens. "
            "Use /history [N] para revisar as antigas."
        )

    while True:
        try:
            question = input("pergunta> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\nOperação cancelada pelo usuário.", file=sys.stderr)
            return 130

        if not question:
            continue
        if question.startswith("/"):
            command = question.lower()
            if command in {"/exit", "/quit"}:
                return 0
            if command == "/clear":
                try:
                    removed = service.clear_conversation(args.workspace_id)
                except WorkspaceNotFoundError as exc:
                    print(f"Erro: {exc}", file=sys.stderr)
                    continue
                print(f"Histórico limpo ({removed} mensagens removidas).")
                continue
            if command == "/sources":
                _print_sources(service, args.workspace_id)
                continue
            if command.startswith("/history"):
                _print_history(service, args.workspace_id, question)
                continue
            if command == "/help":
                print(
                    "Comandos: /sources, /history [N], /clear, /help, /exit. "
                    "Digite uma pergunta para consultar as fontes."
                )
                continue
            print("Comando desconhecido. Use /help.")
            continue

        try:
            # O serviço retoma a conversa salva e grava a nova troca.
            answer = service.ask(
                args.workspace_id,
                question,
                top_k=args.top_k,
            )
        except (ChatServiceError, AiError, ValueError) as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            continue

        _print_answer(answer)


# Imprime a resposta e as fontes citadas.
def _print_answer(answer: ChatAnswer) -> None:
    print()
    print(answer.answer)

    if answer.citations:
        print("\nFontes citadas:")
        for citation in answer.citations:
            location: list[str] = []
            if citation.page_number is not None:
                location.append(f"página {citation.page_number}")
            if citation.section_title:
                location.append(citation.section_title)
            if citation.source_url:
                location.append(citation.source_url)
            suffix = " | " + " | ".join(location) if location else ""
            print(
                f"  [{citation.marker}] {citation.source_title or 'Fonte'}"
                f"{suffix}"
            )

    if answer.warnings:
        print("\nAvisos:")
        for warning in answer.warnings:
            print(f"  - {warning}")
    print()


# Imprime um resumo da indexação.
def _print_status(status: ChatStatus) -> None:
    print(f"Workspace: {status.workspace_id}")
    print(f"Fontes: {status.sources_total} (prontas: {status.sources_ready})")
    print(f"Trechos: {status.chunks_total}")
    print(f"Trechos com embeddings: {status.chunks_embedded}")
    print(f"Modelo de embedding: {status.embedding_model or '(não configurado)'}")


# Exibe as mensagens antigas salvas, opcionalmente limitadas.
def _print_history(service: ChatService, workspace_id: int, raw: str) -> None:
    parts = raw.split(maxsplit=1)
    limit: int | None = 20

    if len(parts) > 1:
        value = parts[1].strip().lower()
        if value in {"all", "tudo"}:
            limit = None
        else:
            try:
                limit = int(value)
            except ValueError:
                print("Uso: /history [N|all]")
                return
            if limit < 1:
                print("O limite deve ser pelo menos 1, ou use 'all'.")
                return

    try:
        records = service.conversation(workspace_id, limit=limit)
    except WorkspaceNotFoundError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return

    if not records:
        print("Nenhuma conversa salva.")
        return

    print(f"\nHistórico ({len(records)} mensagens):")
    for record in records:
        if record.role == "user":
            print(f"\nVocê: {record.content}")
            continue

        answer = answer_from_record(record)
        if answer is not None:
            _print_answer(answer)
        else:
            print(f"\nAgente: {record.content}")


# Lista as fontes do workspace dentro do REPL.
def _print_sources(service: ChatService, workspace_id: int) -> None:
    sources = service.source_repository.list_by_workspace(workspace_id)
    if not sources:
        print("Nenhuma fonte cadastrada.")
        return

    for source in sources:
        print(
            f"  {source.id}: {source.title or '(sem título)'} "
            f"[{source.status.value}]"
        )
