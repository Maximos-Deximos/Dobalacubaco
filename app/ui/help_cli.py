# Comando de ajuda da interface de linha de comando.

from __future__ import annotations

import argparse
import sys

from app.ui.help import render_help


# Exibe a ajuda geral ou a ajuda de um comando específico.
def command_help(args: argparse.Namespace) -> int:
    try:
        print(render_help(tuple(args.topic), show_all=args.show_all))
    except KeyError:
        topic = " ".join(args.topic)
        print(f"Erro: comando '{topic}' não encontrado.", file=sys.stderr)
        print("Use 'help' para ver os comandos disponíveis.", file=sys.stderr)
        return 2
    return 0
