# Comandos de perfil da interface de linha de comando.

from __future__ import annotations

import argparse
import sys

from app.memory.database import init_db
from app.memory.user_repository import (
    ProfileNotFoundError,
    UserRepository,
)
from app.schemas.profile import PROFILE_KEYS, ProfilePatch, UserProfile


# Campos fixos que podem ser alterados diretamente pela CLI.
DIRECT_PROFILE_FIELDS = set(PROFILE_KEYS) - {"links", "skills"}


# Rótulos exibidos por profile show.
PROFILE_LABELS = (
    ("full_name", "Nome completo"),
    ("first_name", "Nome"),
    ("last_name", "Sobrenome"),
    ("email", "E-mail"),
    ("phone", "Telefone"),
    ("organization", "Organização"),
    ("role", "Cargo ou função"),
    ("address", "Endereço"),
    ("city", "Cidade"),
    ("state", "Estado"),
    ("postal_code", "CEP"),
    ("country", "País"),
    ("birth_date", "Data de nascimento"),
)


# Cria o perfil padrão de forma idempotente.
def command_profile_init(_args: argparse.Namespace) -> int:
    init_db()
    repository = UserRepository()
    profile, created = repository.ensure_default()

    if created:
        print(f"Perfil '{profile.name}' criado com sucesso.")
    else:
        print(
            f"Perfil '{profile.name}' já existe. "
            "Use 'profile set' para atualizar."
        )

    return 0


# Exibe o perfil padrão em formato legível ou JSON.
def command_profile_show(args: argparse.Namespace) -> int:
    init_db()
    repository = UserRepository()
    profile = repository.get_default()

    if profile is None:
        print(
            "Nenhum perfil cadastrado. "
            "Execute: python -m app.main profile init",
            file=sys.stderr,
        )
        return 1

    if args.json_output:
        print(profile.model_dump_json(indent=2))
    else:
        _print_profile(profile)

    return 0


# Atualiza campos fixos, links e respostas personalizadas.
def command_profile_set(args: argparse.Namespace) -> int:
    init_db()
    repository = UserRepository()
    profile = repository.get_default()

    if profile is None:
        print(
            "Nenhum perfil cadastrado. "
            "Execute: python -m app.main profile init",
            file=sys.stderr,
        )
        return 1

    try:
        changes = _parse_assignments(args.assignments)
        patch = ProfilePatch(**changes)
        updated = repository.update(profile.id, patch)
    except (ValueError, ProfileNotFoundError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2

    print(f"Perfil '{updated.name}' atualizado com sucesso.")
    return 0


# Converte argumentos no formato chave=valor em um dicionário de alterações.
def _parse_assignments(assignments: list[str]) -> dict[str, object]:
    changes: dict[str, object] = {}
    custom_answers: dict[str, str] = {}
    links: dict[str, str] = {}

    for assignment in assignments:
        if "=" not in assignment:
            raise ValueError(
                f"Atribuição inválida '{assignment}'. Use chave=valor."
            )

        key, raw_value = assignment.split("=", 1)
        key = key.strip()
        value = raw_value.strip()

        if not key:
            raise ValueError("A chave da atribuição não pode ser vazia.")

        if key.startswith("custom."):
            custom_key = key.removeprefix("custom.").strip()
            if not custom_key:
                raise ValueError("Informe o nome após 'custom.'.")
            custom_answers[custom_key] = value
        elif key.startswith("links."):
            link_key = key.removeprefix("links.").strip()
            if not link_key:
                raise ValueError("Informe o nome após 'links.'.")
            links[link_key] = value
        elif key == "skills":
            changes["skills"] = [
                item.strip() for item in value.split(",") if item.strip()
            ]
        elif key in DIRECT_PROFILE_FIELDS:
            changes[key] = value or None
        else:
            allowed = ", ".join(sorted(DIRECT_PROFILE_FIELDS | {"skills"}))
            raise ValueError(
                f"Chave desconhecida '{key}'. "
                f"Chaves fixas: {allowed}. "
                "Use custom.* ou links.* para valores extras."
            )

    if custom_answers:
        changes["custom_answers"] = custom_answers
    if links:
        changes["links"] = links
    if not changes:
        raise ValueError("Nenhuma alteração foi informada.")

    return changes


# Imprime o perfil em formato legível.
def _print_profile(profile: UserProfile) -> None:
    print(f"Perfil: {profile.name} (id={profile.id})")

    has_values = False
    for key, label in PROFILE_LABELS:
        value = getattr(profile, key)
        if value in (None, "", [], {}):
            continue
        has_values = True
        print(f"{label}: {value}")

    if profile.links:
        has_values = True
        print("\nLinks:")
        for key in sorted(profile.links):
            print(f"  {key}: {profile.links[key]}")

    if profile.skills:
        has_values = True
        print("\nHabilidades:")
        print("  " + ", ".join(profile.skills))

    if profile.custom_answers:
        has_values = True
        print("\nRespostas personalizadas:")
        for key in sorted(profile.custom_answers):
            print(f"  {key}: {profile.custom_answers[key]}")

    if not has_values:
        print("Nenhum dado preenchido.")
