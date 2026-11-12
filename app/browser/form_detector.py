# Detecção de campos de formulário presentes na página.

from __future__ import annotations

from playwright.async_api import Page

from app.browser.adapters.google_forms import GoogleFormsAdapter
from app.browser.page_inspector import PageInspector
from app.config import Settings, get_settings
from app.schemas.form import (
    DetectedField,
    DetectedSubField,
    DetectionResult,
    FieldOption,
    FieldType,
    PageSnapshot,
)

# Extrai controles do DOM, agrupa opções e injeta atributos estáveis.
EXTRACTION_SCRIPT = r"""
(args) => {
  const prefix = (args && args.prefix) || "";
  const normalize = (value) => (value || "").replace(/\s+/g, " ").trim().slice(0, 300);
  const cleanLabel = (value) => normalize(value).replace(/\s*\*+\s*$/g, "").trim();
  const genericAnswerLabel = /^(sua resposta|your answer|resposta|answer)$/i;

  const requiredInfo = (element, container) => {
    if (element && element.required) {
      return { required: true, source: "native" };
    }

    if (element && element.getAttribute("aria-required") === "true") {
      return { required: true, source: "aria-required" };
    }

    for (const node of [container, element]) {
      if (node && node.getAttribute("data-required") === "true") {
        return { required: true, source: "data-required" };
      }
      if (node && node.getAttribute("aria-required") === "true") {
        return { required: true, source: "aria-required" };
      }
    }

    return { required: false, source: null };
  };

  const constraintsFor = (element) => {
    const constraints = {};
    if (!element) {
      return constraints;
    }

    for (const name of [
      "min",
      "max",
      "step",
      "pattern",
      "maxlength",
      "minlength"
    ]) {
      const value = element.getAttribute(name);
      if (value) {
        constraints[name] = value;
      }
    }

    return constraints;
  };

  const describedText = (element) => {
    if (!element) {
      return "";
    }

    const ids = (element.getAttribute("aria-describedby") || "")
      .split(/\s+/)
      .filter(Boolean);

    return Array.from(new Set(ids))
      .map((id) => document.getElementById(id))
      .filter(Boolean)
      .map((node) => cleanLabel(node.innerText || node.textContent || ""))
      .filter(Boolean)
      .join(" ");
  };

  const textOf = (element) => normalize(
    element ? (element.innerText || element.textContent || "") : ""
  );

  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    if (
      style.display === "none" ||
      style.visibility === "hidden" ||
      style.opacity === "0"
    ) {
      return false;
    }
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };

  const labeledByText = (element) => {
    const ids = element.getAttribute("aria-labelledby");
    if (!ids) {
      return "";
    }
    return normalize(
      ids
        .split(/\s+/)
        .map((id) => document.getElementById(id))
        .filter(Boolean)
        .map((node) => textOf(node))
        .join(" ")
    );
  };

  const labelText = (element) => {
    if (element.labels && element.labels.length > 0) {
      const label = cleanLabel(element.labels[0].innerText || element.labels[0].textContent);
      if (label) {
        return label;
      }
    }

    const labelledBy = cleanLabel(labeledByText(element));
    if (labelledBy) {
      return labelledBy;
    }

    const ariaLabel = cleanLabel(element.getAttribute("aria-label"));
    if (ariaLabel && !genericAnswerLabel.test(ariaLabel)) {
      return ariaLabel;
    }

    const fieldset = element.closest("fieldset");
    if (fieldset) {
      const legendText = cleanLabel(textOf(fieldset.querySelector("legend")));
      if (legendText) {
        return legendText;
      }
    }

    const item = element.closest(
      '[role="listitem"], .freebirdFormviewerComponentsQuestionBase'
    );
    if (item) {
      const headingText = cleanLabel(
        textOf(
          item.querySelector(
            '[role="heading"], .freebirdFormviewerComponentsQuestionBaseTitle'
          )
        )
      );
      if (headingText) {
        return headingText;
      }
    }

    if (ariaLabel) {
      return ariaLabel;
    }

    const placeholder = cleanLabel(element.getAttribute("placeholder"));
    if (placeholder) {
      return placeholder;
    }

    return cleanLabel(element.getAttribute("name") || element.id || "");
  };

  const optionLabel = (element) => {
    if (element.labels && element.labels.length > 0) {
      const label = cleanLabel(element.labels[0].innerText || element.labels[0].textContent);
      if (label) {
        return label;
      }
    }

    const ariaLabel = cleanLabel(element.getAttribute("aria-label"));
    if (ariaLabel) {
      return ariaLabel;
    }

    const label = element.closest("label");
    if (label) {
      const labelTextValue = cleanLabel(label.innerText || label.textContent);
      if (labelTextValue) {
        return labelTextValue;
      }
    }

    const roleWrapper = element.closest('[role="radio"], [role="checkbox"]');
    if (roleWrapper) {
      const wrapperText = cleanLabel(roleWrapper.innerText || roleWrapper.textContent);
      if (wrapperText) {
        return wrapperText;
      }
    }

    const parent = element.parentElement;
    if (parent) {
      const parentText = cleanLabel(parent.innerText || parent.textContent);
      if (parentText) {
        return parentText;
      }
    }

    return cleanLabel(
      element.getAttribute("value") || element.getAttribute("data-value") || ""
    );
  };

  const containerLabel = (container, fallbackElement) => {
    if (container) {
      const labelledBy = cleanLabel(labeledByText(container));
      if (labelledBy) {
        return labelledBy;
      }

      const headingText = cleanLabel(
        textOf(
          container.querySelector(
            '[role="heading"], legend, .freebirdFormviewerComponentsQuestionBaseTitle'
          )
        )
      );
      if (headingText) {
        return headingText;
      }

      const ariaLabel = cleanLabel(container.getAttribute("aria-label"));
      if (ariaLabel && !genericAnswerLabel.test(ariaLabel)) {
        return ariaLabel;
      }
    }

    return labelText(fallbackElement);
  };

  const typeFor = (element) => {
    const tag = element.tagName.toLowerCase();
    const role = (element.getAttribute("role") || "").toLowerCase();

    if (tag === "textarea") {
      return "textarea";
    }

    if (tag === "select" || role === "combobox" || role === "listbox") {
      return "select";
    }

    if (tag === "input") {
      const inputType = (element.getAttribute("type") || "text").toLowerCase();
      if (["email", "tel", "number", "url", "date", "time"].includes(inputType)) {
        return inputType;
      }
      if (["text", "search", "password"].includes(inputType)) {
        return "text";
      }
      if (inputType === "checkbox") {
        return "checkbox";
      }
      if (inputType === "radio") {
        return "radio";
      }
      if (inputType === "file") {
        return "file";
      }
      return "unknown";
    }

    if (role === "textbox") {
      return "text";
    }

    return "text";
  };

  const selector = [
    "input",
    "textarea",
    "select",
    '[contenteditable="true"]',
    '[role="textbox"]',
    '[role="combobox"]',
    '[role="radio"]',
    '[role="checkbox"]'
  ].join(",");

  const candidates = Array.from(document.querySelectorAll(selector)).filter(
    (element) => {
      if (element.tagName.toLowerCase() !== "input") {
        return true;
      }
      const inputType = (element.getAttribute("type") || "text").toLowerCase();
      return !["hidden", "submit", "button", "reset", "image"].includes(
        inputType
      );
    }
  );

  const groups = new Map();
  const grouped = new Set();

  for (const element of candidates) {
    const tag = element.tagName.toLowerCase();
    const role = (element.getAttribute("role") || "").toLowerCase();
    const inputType =
      tag === "input"
        ? (element.getAttribute("type") || "text").toLowerCase()
        : "";
    const isRadio = inputType === "radio" || role === "radio";
    const isCheckbox = inputType === "checkbox" || role === "checkbox";

    if (!isRadio && !isCheckbox) {
      continue;
    }

    const name = element.getAttribute("name") || "";
    let key;
    let container;

    if (name) {
      key = `${isRadio ? "radio" : "checkbox"}:${name}`;
      container =
        element.closest(
          'fieldset, [role="radiogroup"], [role="group"], [role="listitem"]'
        ) || element.parentElement;
    } else {
      container =
        element.closest(
          '[role="radiogroup"], [role="group"], fieldset, [role="listitem"]'
        ) || element.parentElement;

      if (!container) {
        continue;
      }

      if (!container.dataset.agentGroupKey) {
        container.dataset.agentGroupKey = `container_${groups.size + 1}`;
      }

      key = `${isRadio ? "radio" : "checkbox"}:${container.dataset.agentGroupKey}`;
    }

    if (!groups.has(key)) {
      groups.set(key, { elements: [], container, isRadio });
    }

    groups.get(key).elements.push(element);
    grouped.add(element);
  }

  const descriptors = [];
  let fieldCounter = 0;
  let groupCounter = 0;

  for (const group of groups.values()) {
    groupCounter += 1;
    fieldCounter += 1;

    const groupId = `${prefix}g_${groupCounter}`;
    for (const element of group.elements) {
      element.setAttribute("data-agent-group-id", groupId);
    }

    const first = group.elements[0];
    const fieldId = `${prefix}f_${fieldCounter}`;
    const label = containerLabel(group.container, first);
    const options = group.elements.map((element) => optionLabel(element));
    const optionValues = group.elements.map((element) =>
      cleanLabel(
        element.getAttribute("value") ||
          element.getAttribute("data-value") ||
          optionLabel(element)
      )
    );
    const requiredState = requiredInfo(first, group.container);
    const required =
      requiredState.required ||
      group.elements.some((element) => requiredInfo(element, group.container).required);
    const disabled = group.elements.every(
      (element) =>
        Boolean(element.disabled) ||
        element.getAttribute("aria-disabled") === "true"
    );
    const visible = group.elements.some((element) => isVisible(element));
    const isConsent =
      !group.isRadio &&
      group.elements.length === 1 &&
      /(concordo|aceito|consent|termos|privacidade|autorizo)/i.test(
        `${label} ${options[0] || ""}`
      );
    const fieldType = isConsent
      ? "consent"
      : group.isRadio
        ? "radio"
        : "checkbox";
    const name =
      group.elements
        .map((element) => element.getAttribute("name") || "")
        .find(Boolean) || null;

    descriptors.push({
      field_id: fieldId,
      selector: `[data-agent-group-id="${groupId}"]`,
      label,
      field_type: fieldType,
      required,
      required_source: requiredState.source,
      options,
      option_values: optionValues,
      option_details: [],
      subfields: [],
      placeholder: null,
      name,
      input_type: group.isRadio ? "radio" : "checkbox",
      group_name: name,
      description: describedText(first),
      help_text: describedText(group.container),
      section_title: "",
      question_number: null,
      constraints: {},
      adapter: "generic",
      frame_url: null,
      visible,
      disabled,
      readonly: false
    });
  }

  for (const element of candidates) {
    if (grouped.has(element)) {
      continue;
    }

    fieldCounter += 1;
    const fieldId = `${prefix}f_${fieldCounter}`;
    element.setAttribute("data-agent-field-id", fieldId);

    const tag = element.tagName.toLowerCase();
    const inputType =
      tag === "input"
        ? (element.getAttribute("type") || "text").toLowerCase()
        : "";
    const options = [];
    const optionValues = [];
    const requiredState = requiredInfo(element, element.closest(
      'fieldset, [role="listitem"], .freebirdFormviewerComponentsQuestionBase'
    ));

    if (tag === "select") {
      for (const option of Array.from(element.options)) {
        const optionText = normalize(option.text);
        const optionValue = normalize(option.value);
        if (!optionText || !optionValue) {
          continue;
        }
        options.push(optionText);
        optionValues.push(optionValue);
      }
    }

    descriptors.push({
      field_id: fieldId,
      selector: `[data-agent-field-id="${fieldId}"]`,
      label: labelText(element),
      field_type: typeFor(element),
      required: requiredState.required,
      required_source: requiredState.source,
      options,
      option_values: optionValues,
      option_details: [],
      subfields: [],
      placeholder: element.getAttribute("placeholder"),
      name: element.getAttribute("name"),
      input_type: inputType || null,
      group_name: null,
      description: describedText(element),
      help_text: describedText(element.closest(
        '[role="listitem"], .freebirdFormviewerComponentsQuestionBase'
      )),
      section_title: "",
      question_number: null,
      constraints: constraintsFor(element),
      adapter: "generic",
      frame_url: null,
      visible: isVisible(element),
      disabled:
        Boolean(element.disabled) ||
        element.getAttribute("aria-disabled") === "true",
      readonly:
        Boolean(element.readOnly) ||
        element.getAttribute("aria-readonly") === "true"
    });
  }

  return descriptors;
}
"""


# Adiciona um aviso apenas se ele ainda não estiver na lista.
def _append_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


# Converte um valor textual em um tipo conhecido.
def _field_type(value: object) -> FieldType:
    try:
        return FieldType(str(value or "unknown"))
    except ValueError:
        return FieldType.UNKNOWN


# Converte opções brutas do JavaScript em modelos validados.
def _parse_option_details(raw: object) -> list[FieldOption]:
    details: list[FieldOption] = []
    if not isinstance(raw, list):
        return details

    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        details.append(
            FieldOption(
                label=label,
                value=str(item["value"]) if item.get("value") not in (None, "") else None,
                selector=(
                    str(item["selector"])
                    if item.get("selector") not in (None, "")
                    else None
                ),
                disabled=bool(item.get("disabled", False)),
            )
        )

    return details


# Converte subcampos de datas, horas e grids em modelos validados.
def _parse_subfields(raw: object) -> list[DetectedSubField]:
    subfields: list[DetectedSubField] = []
    if not isinstance(raw, list):
        return subfields

    for item in raw:
        if not isinstance(item, dict):
            continue
        subfield_id = str(item.get("subfield_id") or "").strip()
        selector = str(item.get("selector") or "").strip()
        if not subfield_id or not selector:
            continue
        subfields.append(
            DetectedSubField(
                subfield_id=subfield_id,
                label=str(item.get("label") or ""),
                field_type=_field_type(item.get("field_type")),
                selector=selector,
                required=bool(item.get("required", False)),
                options=_parse_option_details(item.get("options")),
            )
        )

    return subfields


# Converte um campo bruto em modelo da aplicação.
def _build_field(
    raw: dict,
    adapter_name: str,
    frame_url: str,
    section_title: str,
    warnings: list[str],
) -> DetectedField:
    field_type_value = str(raw.get("field_type") or "unknown")
    field_type = _field_type(field_type_value)
    if field_type == FieldType.UNKNOWN and field_type_value != "unknown":
        _append_warning(
            warnings,
            f"Tipo de campo desconhecido: {field_type_value}.",
        )

    option_details = _parse_option_details(raw.get("option_details"))
    raw_options = raw.get("options") or []
    raw_option_values = raw.get("option_values") or []

    options = [str(item) for item in raw_options] if isinstance(raw_options, list) else []
    if not options:
        options = [option.label for option in option_details]

    option_values = (
        [str(item) for item in raw_option_values]
        if isinstance(raw_option_values, list)
        else []
    )
    if not option_values:
        option_values = [
            option.value for option in option_details if option.value is not None
        ]

    constraints = raw.get("constraints")
    if not isinstance(constraints, dict):
        constraints = {}

    return DetectedField(
        field_id=str(raw.get("field_id") or ""),
        selector=str(raw.get("selector") or ""),
        label=str(raw.get("label") or ""),
        field_type=field_type,
        required=bool(raw.get("required", False)),
        options=options,
        option_values=option_values,
        option_details=option_details,
        subfields=_parse_subfields(raw.get("subfields")),
        placeholder=raw.get("placeholder") or None,
        name=raw.get("name") or None,
        input_type=raw.get("input_type") or None,
        group_name=raw.get("group_name") or None,
        description=str(raw.get("description") or ""),
        help_text=str(raw.get("help_text") or raw.get("description") or ""),
        section_title=str(raw.get("section_title") or section_title or ""),
        question_number=raw.get("question_number") or None,
        constraints=constraints,
        required_source=raw.get("required_source") or None,
        adapter=str(raw.get("adapter") or adapter_name),
        frame_url=str(raw.get("frame_url") or frame_url),
        visible=bool(raw.get("visible", True)),
        disabled=bool(raw.get("disabled", False)),
        readonly=bool(raw.get("readonly", False)),
    )


# Detecta campos e metadados de formulário na página atual.
class FormDetector:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.google_adapter = GoogleFormsAdapter()

    # Executa a extração e converte o resultado para os schemas da aplicação.
    async def detect(
        self,
        page: Page,
        page_snapshot: PageSnapshot | None = None,
    ) -> DetectionResult:
        snapshot = page_snapshot or await PageInspector(self.settings).inspect(page)
        warnings = list(snapshot.warnings)
        fields: list[DetectedField] = []
        inspected_frames: list[str] = []
        metadata: dict = {}

        frames = [page.main_frame]
        frames.extend(
            frame
            for frame in page.frames
            if frame != page.main_frame
            and frame.url
            and frame.url != "about:blank"
        )

        for index, frame in enumerate(frames):
            frame_url = frame.url or ""
            is_main = frame == page.main_frame
            is_google = GoogleFormsAdapter.matches(frame_url)

            if not is_main and not is_google:
                continue

            prefix = "" if index == 0 else f"f{index}_"

            try:
                if is_google:
                    payload = await self.google_adapter.extract(frame, prefix)
                    raw_fields = payload.get("fields", [])
                    frame_metadata = payload.get("metadata", {})
                    adapter_name = self.google_adapter.name
                else:
                    raw_fields = await frame.evaluate(
                        EXTRACTION_SCRIPT,
                        {"prefix": prefix},
                    )
                    frame_metadata = {}
                    adapter_name = "generic"
            except Exception as exc:  # noqa: BLE001
                _append_warning(
                    warnings,
                    f"Falha ao inspecionar o frame {frame_url or '(sem URL)'}: {exc}",
                )
                continue

            if not isinstance(raw_fields, list):
                _append_warning(
                    warnings,
                    f"O extrator do frame {frame_url or '(sem URL)'} retornou formato inválido.",
                )
                continue

            inspected_frames.append(frame_url)

            for warning in frame_metadata.get("warnings", []):
                _append_warning(warnings, str(warning))

            for key in (
                "form_title",
                "form_description",
                "section_title",
                "section_description",
                "page_index",
                "has_next",
                "is_google_form",
            ):
                if key not in frame_metadata:
                    continue
                value = frame_metadata[key]
                if key in {"has_next", "is_google_form", "page_index"} or value:
                    metadata[key] = value

            frame_section = (
                frame_metadata.get("section_title")
                or snapshot.section_title
            )

            for raw in raw_fields:
                if not isinstance(raw, dict):
                    continue
                fields.append(
                    _build_field(
                        raw,
                        adapter_name,
                        frame_url,
                        frame_section,
                        warnings,
                    )
                )

        update = dict(metadata)
        update["inspected_frames"] = inspected_frames
        if snapshot.form_count == 0 and metadata.get("is_google_form"):
            update["form_count"] = 1
        snapshot = snapshot.model_copy(update=update)

        if not fields:
            _append_warning(warnings, "Nenhum campo de formulário foi detectado.")

        if any(field.input_type == "file" or field.field_type == FieldType.FILE for field in fields):
            _append_warning(
                warnings,
                "Campos de arquivo foram detectados, mas não são suportados nesta versão.",
            )

        if any(
            field.field_type == FieldType.UNKNOWN and field.input_type != "file"
            for field in fields
        ):
            _append_warning(warnings, "Existem campos com tipo não suportado.")

        if snapshot.has_next and not any("mais de uma seção" in w for w in warnings):
            _append_warning(
                warnings,
                "O formulário possui mais de uma seção; apenas a página atual foi inspecionada.",
            )

        return DetectionResult(
            page=snapshot,
            fields=fields,
            warnings=warnings,
        )
