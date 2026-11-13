# Leitura e preenchimento de campos AcroForm em PDFs.

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.constants import FieldDictionaryAttributes as FDA

from app.schemas.pdf import PdfFieldOption, PdfFieldType, PdfFormField


# Erro lançado quando o PDF não pode ser lido ou preenchido.
class PdfFormError(ValueError):
    pass


# Resultado completo da inspeção de um formulário.
@dataclass(slots=True)
class InspectedPdfForm:
    fields: list[PdfFormField] = field(default_factory=list)
    page_count: int = 0
    warnings: list[str] = field(default_factory=list)


# Lê os campos AcroForm de um PDF.
class PdfFormInspector:
    def inspect(self, content: bytes) -> InspectedPdfForm:
        reader = self._reader(content)
        page_count = len(reader.pages)
        warnings: list[str] = []

        try:
            raw_fields = reader.get_fields()
        except Exception as exc:
            raise PdfFormError(f"Falha ao ler os campos do PDF: {exc}") from exc

        if not raw_fields:
            raise PdfFormError(
                "O PDF não possui campos de formulário AcroForm preenchíveis."
            )

        page_map = self._page_map(reader)
        fields: list[PdfFormField] = []
        for key, raw in raw_fields.items():
            try:
                parsed = self._parse_field(str(key), raw, page_map)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Falha ao interpretar o campo '{key}': {exc}")
                continue
            if parsed is not None:
                fields.append(parsed)

        if not fields:
            raise PdfFormError(
                "O PDF possui AcroForm, mas nenhum campo pôde ser interpretado."
            )

        return InspectedPdfForm(
            fields=fields,
            page_count=page_count,
            warnings=warnings,
        )

    # Abre o PDF e tenta desbloquear senhas vazias.
    def _reader(self, content: bytes) -> PdfReader:
        try:
            reader = PdfReader(BytesIO(content))
        except Exception as exc:
            raise PdfFormError(f"PDF inválido: {exc}") from exc

        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:
                raise PdfFormError("PDF protegido por senha.") from exc
            if not unlocked:
                raise PdfFormError("PDF protegido por senha.")
        return reader

    # Mapeia o nome do campo para a página onde ele aparece.
    def _page_map(self, reader: PdfReader) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for page_number, page in enumerate(reader.pages, start=1):
            annotations = page.get("/Annots", []) or []
            for annotation in annotations:
                name = self._safe_annotation_name(annotation)
                if name and name not in mapping:
                    mapping[name] = page_number
        return mapping

    # Extrai o nome de uma anotação sem interromper a inspeção.
    def _safe_annotation_name(self, annotation: Any) -> str:
        try:
            return self._annotation_name(annotation.get_object())
        except Exception:  # noqa: BLE001
            return ""

    # Obtém o nome do campo a partir do widget ou do pai.
    def _annotation_name(self, annotation: Any) -> str:
        direct = annotation.get("/T")
        if direct:
            return str(direct)
        parent = annotation.get("/Parent")
        if parent is not None:
            parent = parent.get_object()
            direct = parent.get("/T")
            if direct:
                return str(direct)
        return ""

    # Converte um dicionário de campo do pypdf no contrato interno.
    def _parse_field(
        self,
        field_name: str,
        raw: Any,
        page_map: dict[str, int],
    ) -> PdfFormField | None:
        if not isinstance(raw, dict):
            return None

        ft = str(raw.get("/FT") or "")
        flags = int(raw.get("/Ff") or 0)
        readonly = bool(flags & int(FDA.FfBits.ReadOnly))
        required = bool(flags & int(FDA.FfBits.Required))
        label = str(raw.get("/TU") or raw.get("/TM") or field_name).strip()
        current = self._normalize_value(raw.get("/V"))
        options, option_warnings = self._options(raw, ft)
        warnings = list(option_warnings)

        if ft == "/Tx":
            field_type = (
                PdfFieldType.TEXTAREA
                if flags & int(FDA.FfBits.Multiline)
                else PdfFieldType.TEXT
            )
        elif ft == "/Btn":
            if flags & int(FDA.FfBits.Pushbutton):
                field_type = PdfFieldType.UNKNOWN
                warnings.append("Botão de ação não é preenchível.")
            elif flags & int(FDA.FfBits.Radio):
                field_type = PdfFieldType.RADIO
            else:
                field_type = PdfFieldType.CHECKBOX
        elif ft == "/Ch":
            field_type = PdfFieldType.CHOICE
        elif ft == "/Sig":
            field_type = PdfFieldType.SIGNATURE
            warnings.append("Campos de assinatura ainda não são suportados.")
        else:
            field_type = PdfFieldType.UNKNOWN
            warnings.append(f"Tipo de campo não suportado: {ft or 'desconhecido'}.")

        max_length = raw.get("/MaxLen")
        try:
            max_len = int(max_length) if max_length is not None else None
        except (TypeError, ValueError):
            max_len = None

        return PdfFormField(
            field_name=field_name,
            label=label,
            field_type=field_type,
            required=required,
            readonly=readonly,
            current_value=current,
            options=options,
            page_number=page_map.get(field_name),
            max_length=max_len,
            warnings=warnings,
        )

    # Normaliza valores NameObject e arrays em texto simples.
    def _normalize_value(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            parts = [self._normalize_value(item) for item in value]
            return ", ".join(part for part in parts if part)
        text = str(value).strip()
        text = text.removeprefix("/")
        if text == "Off":
            return "Off"
        return text or None

    # Extrai opções de escolha ou estados de botões.
    def _options(self, raw: dict[str, Any], ft: str) -> tuple[list[PdfFieldOption], list[str]]:
        warnings: list[str] = []
        options: list[PdfFieldOption] = []

        raw_options = raw.get("/Opt")
        if raw_options:
            for item in raw_options:
                option = self._option_from_item(item)
                if option is not None:
                    options.append(option)

        if ft == "/Btn" and not options:
            states = raw.get("/_States_") or []
            for state in states:
                value = self._normalize_value(state)
                if value and value != "Off":
                    options.append(PdfFieldOption(label=value, value=value))

        if ft == "/Ch" and not options:
            warnings.append("Campo de escolha sem opções declaradas no PDF.")

        return options, warnings

    # Converte uma opção bruta em rótulo e valor exportado.
    def _option_from_item(self, item: Any) -> PdfFieldOption | None:
        try:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                label = self._normalize_value(item[0]) or ""
                value = self._normalize_value(item[1]) or label
            else:
                label = self._normalize_value(item) or ""
                value = label
        except Exception:  # noqa: BLE001
            return None
        if not value:
            return None
        return PdfFieldOption(label=label or value, value=value)


# Preenche os campos de um PDF preservando o documento original.
class PdfFormFiller:
    def fill(
        self,
        content: bytes,
        values: dict[str, str],
        *,
        flatten: bool = False,
    ) -> bytes:
        if not values:
            raise PdfFormError("Nenhum valor aprovado para preencher.")

        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                unlocked = reader.decrypt("")
                if not unlocked:
                    raise PdfFormError("PDF protegido por senha.")
            writer = PdfWriter(clone_from=reader)
            raw_fields = reader.get_fields() or {}
            button_fields = {
                str(name)
                for name, raw in raw_fields.items()
                if isinstance(raw, dict) and str(raw.get("/FT") or "") == "/Btn"
            }
            normalized = {
                name: (
                    value
                    if name not in button_fields or value.startswith("/")
                    else f"/{value}"
                )
                for name, value in values.items()
            }
            target_pages = [page for page in writer.pages if "/Annots" in page]
            writer.update_page_form_field_values(
                target_pages,
                normalized,
                auto_regenerate=True,
                flatten=flatten,
            )
            output = BytesIO()
            writer.write(output)
            return output.getvalue()
        except PdfFormError:
            raise
        except Exception as exc:
            raise PdfFormError(f"Falha ao preencher o PDF: {exc}") from exc
