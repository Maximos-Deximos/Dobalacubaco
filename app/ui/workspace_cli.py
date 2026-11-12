# Comandos de workspace da interface de linha de comando.

from __future__ import annotations

import argparse
import json
import sys

from app.application.workspace_service import WorkspaceService
from app.memory.database import init_db
from app.memory.workspace_repository import (
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
)


# Cria um novo workspace.
def command_workspace_new(args: argparse.Namespace) -> int:
    init_db()
    service = WorkspaceService()

    try:
        workspace = service.create(args.name, args.description)
    except WorkspaceAlreadyExistsError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2

    print(
        f"Workspace '{workspace.name}' criado com sucesso "
        f"(id={workspace.id})."
    )
    return 0


# Lista os workspaces cadastrados.
def command_workspace_list(args: argparse.Namespace) -> int:
    init_db()
    service = WorkspaceService()
    workspaces = service.list_all()

    if args.json_output:
        print(
            json.dumps(
                [workspace.model_dump(mode="json") for workspace in workspaces],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not workspaces:
        print("Nenhum workspace cadastrado.")
        return 0

    for workspace in workspaces:
        print(
            f"{workspace.id:<5} {workspace.name:<40} "
            f"{workspace.status.value:<10} {workspace.description}"
        )
    return 0


# Exibe um workspace específico.
def command_workspace_show(args: argparse.Namespace) -> int:
    init_db()
    service = WorkspaceService()

    try:
        workspace = service.get(args.workspace_id)
    except WorkspaceNotFoundError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(workspace.model_dump_json(indent=2))
        return 0

    print(f"ID: {workspace.id}")
    print(f"Nome: {workspace.name}")
    print(f"Status: {workspace.status.value}")
    print(f"Descrição: {workspace.description or '(sem descrição)'}")
    print(f"Criado em: {workspace.created_at.isoformat()}")
    print(f"Atualizado em: {workspace.updated_at.isoformat()}")
    return 0
