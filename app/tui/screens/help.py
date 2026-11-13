# Tela de ajuda da interface de terminal.

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Markdown

from app.ui.help import render_global_help

TUI_HELP = """
## Atalhos da interface

- `?` ou `F1`: abre esta ajuda.
- `q`: sai da aplicação.
- `Esc`: volta para a tela anterior.
- `Enter`: abre o item selecionado.
- `n`: cria um novo item no contexto atual.
- `d`: exclui o item ou a fonte selecionada, com confirmação.
- `a`: adiciona uma fonte por URL.
- `f`: adiciona um arquivo PDF ou HTML local.
- `i`: indexa as fontes da área de trabalho.
- `r`: atualiza a tela atual.
- `Ctrl+L`: limpa a conversa.
- `w`: abre a lista de áreas de trabalho.
- `p`: abre a lista global de propostas.
- `t`: abre as ferramentas de diagnóstico e inspeção.
- `u`: abre o perfil local.
- `Tab` e setas: navegam entre campos e listas.

## Fluxo sugerido

1. Crie uma área de trabalho.
2. Adicione o edital por URL ou arquivo local.
3. Indexe as fontes.
4. Converse com o agente na aba de conversa.
5. Crie e consulte a proposta de solução.
"""


# Tela de ajuda compartilhando o registro central da CLI.
class HelpScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "back", "Voltar")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="help-body"):
            yield Markdown(render_global_help() + "\n\n" + TUI_HELP)
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()
