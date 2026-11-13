# Comando de inspeção de formulários da CLI.

from __future__ import annotations

import argparse
import sys

from app.application.inspection_service import InspectionService
from app.browser.browser_manager import BrowserLaunchError
from app.browser.page_inspector import InvalidUrlError, NavigationError
from app.schemas.form import DetectionResult


# Executa a inspeção e imprime o resultado.
def command_inspect(args: argparse.Namespace) -> int:
    try:
        result = InspectionService().inspect_sync(args.url)
    except (InvalidUrlError, NavigationError, BrowserLaunchError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Erro inesperado: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(result.model_dump_json(indent=2))
    elif args.debug_output:
        _print_debug(result)
    else:
        _print_result(result)

    return 0


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


# Imprime todos os detalhes usados pelo inspetor no modo de debug.
def _print_debug(result: DetectionResult) -> None:
    page = result.page
    print("=== Modo debug do inspetor ===")
    print(f"URL: {page.url}")
    print(f"Título: {page.title or '(sem título)'}")
    print(f"Título do formulário: {page.form_title or '(não detectado)'}")
    print(f"Seção: {page.section_title or '(não detectada)'}")
    print(f"Google Forms: {'sim' if page.is_google_form else 'não'}")
    print(f"Página: {page.page_index}")
    print(f"Possui próxima seção: {'sim' if page.has_next else 'não'}")
    print(f"Formulários: {page.form_count}")
    print(f"Campos detectados: {len(result.fields)}")

    if page.inspected_frames:
        print("Frames inspecionados:")
        for frame_url in page.inspected_frames:
            print(f"  - {frame_url or '(sem URL)'}")

    if result.warnings:
        print("\nAvisos:")
        for warning in result.warnings:
            print(f"  - {warning}")

    for field in result.fields:
        print("\n--- Campo ---")
        print(f"ID: {field.field_id}")
        print(f"Adaptador: {field.adapter}")
        print(f"Rótulo: {field.label or '(sem rótulo)'}")
        print(f"Tipo: {field.field_type.value}")
        print(f"Obrigatório: {'sim' if field.required else 'não'}")
        print(f"Origem da obrigatoriedade: {field.required_source or '(não informada)'}")
        print(f"Seletor: {field.selector}")
        print(f"Frame: {field.frame_url or '(principal)'}")
        print(f"Seção: {field.section_title or '(não detectada)'}")
        print(f"Pergunta: {field.question_number or '(não numerada)'}")
        print(f"input_type: {field.input_type or '(não informado)'}")
        print(f"name: {field.name or '(não informado)'}")
        print(f"placeholder: {field.placeholder or '(não informado)'}")
        print(f"Visível: {'sim' if field.visible else 'não'}")
        print(f"Desabilitado: {'sim' if field.disabled else 'não'}")
        print(f"Somente leitura: {'sim' if field.readonly else 'não'}")

        if field.description:
            print(f"Descrição: {field.description}")
        if field.help_text:
            print(f"Ajuda: {field.help_text}")
        if field.constraints:
            print(f"Restrições: {field.constraints}")

        if field.option_details:
            print("Opções:")
            for option in field.option_details:
                print(
                    f"  - {option.label!r} valor={option.value!r} "
                    f"seletor={option.selector!r} "
                    f"desabilitada={'sim' if option.disabled else 'não'}"
                )
        elif field.options:
            print(f"Opções: {', '.join(field.options)}")

        if field.subfields:
            print("Subcampos:")
            for subfield in field.subfields:
                print(
                    f"  - {subfield.subfield_id} tipo={subfield.field_type.value} "
                    f"obrigatório={'sim' if subfield.required else 'não'} "
                    f"rótulo={subfield.label!r} seletor={subfield.selector}"
                )
                for option in subfield.options:
                    print(
                        f"      opção {option.label!r} valor={option.value!r} "
                        f"seletor={option.selector!r}"
                    )
