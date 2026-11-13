# Comandos de inspeção, sugestão e preenchimento de PDFs.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.application.pdf_form_service import PdfFormService, PdfFormServiceError
from app.memory.database import init_db
from app.memory.pdf_form_repository import PdfFormNotFoundError
from app.memory.source_repository import SourceNotFoundError
from app.schemas.pdf import (
    PdfFormInspection,
    PdfFormSessionDetail,
)


# Executa a inspeção dos campos de uma fonte PDF.
def command_pdf_fields(args: argparse.Namespace) -> int:
    init_db()
    try:
        inspection = PdfFormService().inspect_source(args.source_id)
    except (PdfFormServiceError, SourceNotFoundError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(inspection.model_dump_json(indent=2))
    else:
        _print_inspection(inspection)
    return 0


# Gera sugestões persistidas para uma sessão de preenchimento.
def command_pdf_suggest(args: argparse.Namespace) -> int:
    init_db()
    service = PdfFormService()
    try:
        session = service.open_session(
            args.source_id,
            instructions=args.instructions,
            force_new=args.new,
        )
        warnings: list[str] = []
        for batch in service.suggest_live(session.id, refresh=args.refresh):
            warnings = batch.warnings
        detail = service.get_session(session.id)
    except (
        PdfFormServiceError,
        PdfFormNotFoundError,
        SourceNotFoundError,
        ValueError,
    ) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    payload = {
        "session": detail.model_dump(mode="json"),
        "warnings": _dedupe(warnings),
    }
    if args.output:
        try:
            path = Path(args.output).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"Erro ao gravar sugestões: {exc}", file=sys.stderr)
            return 1

    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_session(detail, warnings)
        if args.output:
            print(f"\nSugestões gravadas em: {Path(args.output).expanduser()}")
    return 0


# Exibe uma sessão persistida.
def command_pdf_show(args: argparse.Namespace) -> int:
    init_db()
    try:
        detail = PdfFormService().get_session(args.session_id)
    except PdfFormNotFoundError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(detail.model_dump_json(indent=2))
    else:
        _print_session(detail, [])
    return 0


# Atualiza manualmente um campo da sessão.
def command_pdf_set(args: argparse.Namespace) -> int:
    init_db()
    service = PdfFormService()
    try:
        field = service.update_field_live(
            args.session_id,
            args.field_name,
            args.value,
        )
        if args.approve:
            field = service.approve_field(args.session_id, args.field_name)
    except (PdfFormServiceError, PdfFormNotFoundError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(field.model_dump_json(indent=2))
    else:
        print(
            f"{field.field_name}: {field.final_value or '(vazio)'} "
            f"[{field.status.value}]"
        )
    return 0


# Aprova um ou todos os campos de uma sessão.
def command_pdf_approve(args: argparse.Namespace) -> int:
    init_db()
    service = PdfFormService()
    try:
        if args.all:
            detail = service.approve_all(args.session_id)
        elif args.field_name:
            service.approve_field(args.session_id, args.field_name)
            detail = service.get_session(args.session_id)
        else:
            print("Erro: informe --all ou --field.", file=sys.stderr)
            return 1
    except (PdfFormServiceError, PdfFormNotFoundError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(detail.model_dump_json(indent=2))
    else:
        _print_session(detail, [])
    return 0


# Grava uma cópia preenchida do PDF.
def command_pdf_fill(args: argparse.Namespace) -> int:
    init_db()
    service = PdfFormService()
    overrides: dict[str, str] | None = None
    if args.values:
        try:
            overrides = _load_values(Path(args.values))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print(f"Erro ao ler valores: {exc}", file=sys.stderr)
            return 1

    try:
        result = service.fill(
            args.session_id,
            args.output,
            flatten=args.flatten,
            overrides=overrides,
        )
    except (PdfFormServiceError, PdfFormNotFoundError, SourceNotFoundError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(result.model_dump_json(indent=2))
    else:
        print(f"PDF preenchido: {result.output_path}")
        print(f"Campos preenchidos: {result.fields_filled}")
        print(f"Campos ignorados: {result.fields_skipped}")
        for warning in result.warnings:
            print(f"Aviso: {warning}")
    return 0


# Imprime um resumo dos campos encontrados no PDF.
def _print_inspection(inspection: PdfFormInspection) -> None:
    print(f"Fonte: {inspection.source_id} — {inspection.source_title or '(sem título)'}")
    print(f"Páginas: {inspection.page_count}")
    print(f"Campos: {len(inspection.fields)}")
    if inspection.warnings:
        print("\nAvisos:")
        for warning in inspection.warnings:
            print(f"  - {warning}")

    print("\nCampos encontrados:")
    for field in inspection.fields:
        required = "sim" if field.required else "não"
        readonly = "sim" if field.readonly else "não"
        print(
            f"  {field.field_name:<24} {field.field_type.value:<10} "
            f"obrigatório={required:<3} somente_leitura={readonly:<3} "
            f"{field.label or '(sem rótulo)'}"
        )
        if field.options:
            values = ", ".join(option.value for option in field.options)
            print(f"      opções: {values}")


# Imprime uma sessão e seus campos.
def _print_session(detail: PdfFormSessionDetail, warnings: list[str]) -> None:
    print(f"Sessão: {detail.id}")
    print(f"Fonte: {detail.source_id} — {detail.source_title or '(sem título)'}")
    print(f"Status: {detail.status.value}")
    print(f"Geração: {detail.generation_status.value}")
    print(f"Progresso: {detail.generation_progress}/{detail.generation_total}")
    if detail.output_path:
        print(f"Saída: {detail.output_path}")
    if detail.error:
        print(f"Erro: {detail.error}")

    print("\nCampos:")
    for field in detail.fields:
        value = field.final_value or field.suggested_value or "(vazio)"
        confidence = (
            f"{field.confidence:.2f}" if field.confidence is not None else "-"
        )
        print(
            f"  {field.field_name:<24} [{field.status.value:<10}] "
            f"confiança={confidence:<5} {value}"
        )
        if field.rationale:
            print(f"      {field.rationale}")

    unique = _dedupe(warnings)
    if unique:
        print("\nAvisos:")
        for warning in unique:
            print(f"  - {warning}")


# Lê um JSON simples de valores ou um objeto com a chave "values".
def _load_values(path: Path) -> dict[str, str]:
    data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("values"), dict):
        data = data["values"]
    if not isinstance(data, dict):
        raise TypeError("O arquivo deve conter um objeto JSON de campo para valor.")
    values: dict[str, str] = {}
    for key, value in data.items():
        if value is None:
            continue
        if not isinstance(value, (str, int, float, bool)):
            raise TypeError(f"Valor inválido para o campo '{key}'.")
        values[str(key)] = str(value)
    return values


# Remove itens duplicados preservando a ordem.
def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
