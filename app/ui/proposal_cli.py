# Comandos de proposta da interface de linha de comando.

from __future__ import annotations

import argparse
import json
import sys

from app.application.proposal_service import ProposalService
from app.memory.database import init_db
from app.memory.proposal_repository import ProposalNotFoundError
from app.memory.workspace_repository import WorkspaceNotFoundError
from app.schemas.proposal import Proposal, ProposalDetail, ProposalSection


# Cria uma proposta com a estrutura inicial de seções.
def command_proposal_new(args: argparse.Namespace) -> int:
    init_db()
    service = ProposalService()

    try:
        proposal = service.create(
            args.workspace_id,
            args.title,
            args.description,
        )
    except WorkspaceNotFoundError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(proposal.model_dump_json(indent=2))
        return 0

    print(
        f"Proposta '{proposal.title}' criada (id={proposal.id}) "
        f"com {len(proposal.sections)} seção(ões)."
    )
    return 0


# Lista todas as propostas ou as de um workspace.
def command_proposal_list(args: argparse.Namespace) -> int:
    init_db()
    service = ProposalService()

    try:
        if args.workspace_id is None:
            proposals = service.list_all()
        else:
            proposals = service.list_by_workspace(args.workspace_id)
    except WorkspaceNotFoundError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(
            json.dumps(
                [proposal.model_dump(mode="json") for proposal in proposals],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not proposals:
        print("Nenhuma proposta cadastrada.")
        return 0

    for proposal in proposals:
        print(
            f"{proposal.id:<5} {proposal.workspace_id:<5} "
            f"{proposal.status.value:<11} {proposal.title}"
        )
    return 0


# Exibe os dados de uma proposta e o estado das seções.
def command_proposal_show(args: argparse.Namespace) -> int:
    init_db()
    service = ProposalService()

    try:
        proposal = service.get(args.proposal_id)
    except ProposalNotFoundError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(proposal.model_dump_json(indent=2))
        return 0

    _print_proposal(proposal)
    return 0


# Exibe apenas o sumário de seções.
def command_proposal_outline(args: argparse.Namespace) -> int:
    init_db()
    service = ProposalService()

    try:
        sections = service.outline(args.proposal_id)
    except ProposalNotFoundError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(
            json.dumps(
                [section.model_dump(mode="json") for section in sections],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    _print_sections(sections)
    return 0


# Imprime os dados principais da proposta.
def _print_proposal(proposal: ProposalDetail) -> None:
    _print_header(proposal)
    print(f"Descrição: {proposal.description or '(sem descrição)'}")
    print(f"Revisão atual: {proposal.current_revision}")
    print()
    _print_sections(proposal.sections)


# Imprime o cabeçalho compartilhado.
def _print_header(proposal: Proposal) -> None:
    print(f"ID: {proposal.id}")
    print(f"Workspace: {proposal.workspace_id}")
    print(f"Título: {proposal.title}")
    print(f"Status: {proposal.status.value}")


# Imprime o sumário de seções com uma prévia do conteúdo.
def _print_sections(sections: list[ProposalSection]) -> None:
    if not sections:
        print("Nenhuma seção cadastrada.")
        return

    for section in sections:
        content = section.content.strip()
        print(
            f"{section.position:>2}. {section.title} "
            f"[{section.key}] status={section.status.value} "
            f"chars={len(section.content)}"
        )
        if content:
            preview = content[:280].replace("\n", " ")
            if len(content) > len(preview):
                preview += "..."
            print(f"    {preview}")
