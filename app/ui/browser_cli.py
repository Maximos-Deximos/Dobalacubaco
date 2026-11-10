# Comando de inspeção de formulários da CLI.

from __future__ import annotations

import argparse
import asyncio
import sys

from app.browser.browser_manager import BrowserLaunchError, BrowserManager
from app.browser.form_detector import FormDetector
from app.browser.page_inspector import (
    InvalidUrlError,
    NavigationError,
    PageInspector,
    validate_url,
)
from app.schemas.form import DetectionResult


# Executa a inspeção e imprime o resultado.
def command_inspect(args: argparse.Namespace) -> int:
    try:
        result = asyncio.run(_inspect_url(args.url))
    except (InvalidUrlError, NavigationError, BrowserLaunchError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Erro inesperado: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(result.model_dump_json(indent=2))
    else:
        _print_result(result)

    return 0


# Executa navegação e detecção dentro do ciclo assíncrono.
async def _inspect_url(url: str) -> DetectionResult:
    safe_url = validate_url(url)

    async with BrowserManager() as manager:
        page = await manager.new_page()
        inspector = PageInspector()
        snapshot = await inspector.navigate(page, safe_url)
        detector = FormDetector()
        return await detector.detect(page, snapshot)


# Imprime um resumo legível dos campos detectados.
def _print_result(result: DetectionResult) -> None:
    print(f"URL: {result.page.url}")
    print(f"Título: {result.page.title or '(sem título)'}")
    print(f"Formulários: {result.page.form_count}")
    print(f"Campos: {len(result.fields)}")

    if result.page.iframe_urls:
        print(f"Iframes: {len(result.page.iframe_urls)}")

    if result.warnings:
        print("\nAvisos:")
        for warning in result.warnings:
            print(f"  - {warning}")

    if not result.fields:
        return

    print("\nCampos detectados:")
    for field in result.fields:
        required = "sim" if field.required else "não"
        label = field.label or "(sem rótulo)"
        print(
            f"  {field.field_id:<5} {field.field_type.value:<10} "
            f"obrigatório={required:<3} {label}"
        )
        if field.options:
            print(f"        opções: {', '.join(field.options)}")
