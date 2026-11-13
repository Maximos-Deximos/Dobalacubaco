# Registro central de ajuda compartilhado pela CLI e pela TUI.

from __future__ import annotations

from dataclasses import dataclass, field


# Descrição de um comando exibida na ajuda.
@dataclass(frozen=True)
class CommandHelp:
    name: str
    summary: str
    usage: str
    category: str = "Geral"
    examples: tuple[str, ...] = field(default_factory=tuple)
    related: tuple[str, ...] = field(default_factory=tuple)


HELP_ENTRIES: tuple[CommandHelp, ...] = (
    CommandHelp(
        name="help",
        summary="exibe a ajuda geral ou de um comando",
        usage="help [comando ...] [--all]",
        examples=(
            "help",
            "help proposal",
            "help proposal new",
        ),
    ),
    CommandHelp(
        name="tui",
        summary="abre a interface de terminal",
        usage="tui",
        examples=("tui",),
        related=("help",),
    ),
    CommandHelp(
        name="doctor",
        summary="verifica configuração, banco, Ollama e Playwright",
        usage="doctor",
        examples=("doctor",),
    ),
    CommandHelp(
        name="profile init",
        summary="cria o perfil local padrão",
        usage="profile init",
        category="Perfil",
    ),
    CommandHelp(
        name="profile show",
        summary="exibe o perfil local",
        usage="profile show [--json]",
        category="Perfil",
    ),
    CommandHelp(
        name="profile set",
        summary="atualiza campos do perfil local",
        usage="profile set CHAVE=VALOR [CHAVE=VALOR ...]",
        category="Perfil",
    ),
    CommandHelp(
        name="inspect",
        summary="inspeciona campos de formulário de uma URL HTTPS",
        usage="inspect URL [--json] [--debug]",
        category="Inspeção",
    ),
    CommandHelp(
        name="workspace new",
        summary="cria uma área de trabalho de edital",
        usage="workspace new NOME [--description TEXTO]",
        category="Áreas de trabalho",
    ),
    CommandHelp(
        name="workspace list",
        summary="lista as áreas de trabalho",
        usage="workspace list [--json]",
        category="Áreas de trabalho",
    ),
    CommandHelp(
        name="workspace show",
        summary="exibe uma área de trabalho",
        usage="workspace show WORKSPACE_ID [--json]",
        category="Áreas de trabalho",
    ),
    CommandHelp(
        name="source add",
        summary="ingere uma URL pública",
        usage="source add URL --workspace ID [--browser] [--follow-pdfs] [--max-links N]",
        category="Fontes",
    ),
    CommandHelp(
        name="source add-file",
        summary="ingere um arquivo HTML ou PDF local",
        usage="source add-file CAMINHO --workspace ID",
        category="Fontes",
    ),
    CommandHelp(
        name="source index",
        summary="cria ou atualiza o índice de busca",
        usage="source index --workspace ID [--source ID] [--force] [--json]",
        category="Fontes",
    ),
    CommandHelp(
        name="source list",
        summary="lista as fontes de uma área de trabalho",
        usage="source list --workspace ID [--json]",
        category="Fontes",
    ),
    CommandHelp(
        name="source show",
        summary="exibe uma fonte e seu snapshot",
        usage="source show SOURCE_ID [--json]",
        category="Fontes",
    ),
    CommandHelp(
        name="chat ask",
        summary="faz uma pergunta à área de trabalho indexada",
        usage="chat ask PERGUNTA --workspace ID [--top-k N] [--json]",
        category="Chat",
    ),
    CommandHelp(
        name="chat repl",
        summary="inicia uma conversa interativa",
        usage="chat repl --workspace ID [--top-k N]",
        category="Chat",
    ),
    CommandHelp(
        name="chat status",
        summary="exibe a situação do índice da área de trabalho",
        usage="chat status --workspace ID [--json]",
        category="Chat",
    ),
    CommandHelp(
        name="proposal new",
        summary="cria uma proposta com a estrutura inicial",
        usage="proposal new --workspace ID --title TITULO [--description TEXTO]",
        category="Propostas",
        examples=(
            "proposal new --workspace 1 --title \"Proposta de inovação\"",
        ),
    ),
    CommandHelp(
        name="proposal list",
        summary="lista as propostas",
        usage="proposal list [--workspace ID] [--json]",
        category="Propostas",
    ),
    CommandHelp(
        name="proposal show",
        summary="exibe uma proposta e suas seções",
        usage="proposal show PROPOSAL_ID [--json]",
        category="Propostas",
    ),
    CommandHelp(
        name="proposal outline",
        summary="exibe o sumário de seções da proposta",
        usage="proposal outline PROPOSAL_ID [--json]",
        category="Propostas",
        related=("proposal show",),
    ),
)


HELP_BY_NAME = {entry.name: entry for entry in HELP_ENTRIES}


# Ordena e agrupa comandos por categoria para a ajuda geral.
def _group_entries(
    entries: list[CommandHelp],
) -> list[tuple[str, list[CommandHelp]]]:
    categories: dict[str, list[CommandHelp]] = {}
    for entry in entries:
        categories.setdefault(entry.category, []).append(entry)
    return sorted(categories.items())


# Renderiza uma entrada individual com exemplos e comandos relacionados.
def _render_entry(entry: CommandHelp) -> str:
    lines = [
        f"{entry.name} — {entry.summary}",
        "",
        f"Uso: {entry.usage}",
    ]
    if entry.examples:
        lines.extend(["", "Exemplos:"])
        lines.extend(f"  {example}" for example in entry.examples)
    if entry.related:
        lines.extend(["", f"Veja também: {', '.join(entry.related)}"])
    return "\n".join(lines)


# Renderiza a ajuda geral agrupada por categoria.
def render_global_help() -> str:
    lines = [
        "Agente de Editais — Ajuda",
        "",
        "Uso: python -m app.main <comando> [opções]",
        "Sem argumentos, abre a interface de terminal (TUI).",
        "",
    ]
    for category, entries in _group_entries(list(HELP_ENTRIES)):
        lines.append(f"{category}:")
        for entry in entries:
            lines.append(f"  {entry.name:<20} {entry.summary}")
        lines.append("")
    lines.extend(
        [
            "Use 'help <comando>' para detalhes, por exemplo:",
            "  python -m app.main help proposal new",
        ]
    )
    return "\n".join(lines).rstrip()


# Renderiza a ajuda de um comando ou de um grupo de comandos.
def render_help(topic: tuple[str, ...] = (), *, show_all: bool = False) -> str:
    if show_all or not topic:
        if show_all:
            entries = sorted(HELP_ENTRIES, key=lambda entry: entry.name)
            return "\n\n".join(_render_entry(entry) for entry in entries)
        return render_global_help()

    name = " ".join(topic).strip()
    exact = HELP_BY_NAME.get(name)
    if exact is not None:
        return _render_entry(exact)

    prefix = f"{name} "
    matches = sorted(
        (
            entry
            for entry in HELP_ENTRIES
            if entry.name.startswith(prefix)
        ),
        key=lambda entry: entry.name,
    )
    if not matches:
        raise KeyError(name)

    lines = [f"Comandos de '{name}':", ""]
    for entry in matches:
        lines.append(f"  {entry.name:<20} {entry.summary}")
    lines.extend(
        [
            "",
            f"Use 'help {name} <subcomando>' para detalhes.",
        ]
    )
    return "\n".join(lines)
