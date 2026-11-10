# Detecção de campos de formulário presentes na página.

from __future__ import annotations

from playwright.async_api import Page

from app.browser.page_inspector import PageInspector
from app.config import Settings, get_settings
from app.schemas.form import DetectionResult, DetectedField, FieldType, PageSnapshot


# Extrai controles do DOM, agrupa opções e injeta atributos estáveis.
EXTRACTION_SCRIPT = r"""
() => {
  const normalize = (value) => (value || "").replace(/\s+/g, " ").trim().slice(0, 300);

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
      return textOf(element.labels[0]);
    }

    const ariaLabel = element.getAttribute("aria-label");
    if (ariaLabel) {
      return normalize(ariaLabel);
    }

    const labelledBy = labeledByText(element);
    if (labelledBy) {
      return labelledBy;
    }

    const fieldset = element.closest("fieldset");
    if (fieldset) {
      const legendText = textOf(fieldset.querySelector("legend"));
      if (legendText) {
        return legendText;
      }
    }

    const item = element.closest(
      '[role="listitem"], .freebirdFormviewerComponentsQuestionBase'
    );
    if (item) {
      const headingText = textOf(
        item.querySelector(
          '[role="heading"], .freebirdFormviewerComponentsQuestionBaseTitle'
        )
      );
      if (headingText) {
        return headingText;
      }
    }

    const placeholder = element.getAttribute("placeholder");
    if (placeholder) {
      return normalize(placeholder);
    }

    return normalize(element.getAttribute("name") || element.id || "");
  };

  const optionLabel = (element) => {
    if (element.labels && element.labels.length > 0) {
      return textOf(element.labels[0]);
    }

    const ariaLabel = element.getAttribute("aria-label");
    if (ariaLabel) {
      return normalize(ariaLabel);
    }

    const label = element.closest("label");
    if (label) {
      return textOf(label);
    }

    const roleWrapper = element.closest('[role="radio"], [role="checkbox"]');
    if (roleWrapper) {
      return textOf(roleWrapper);
    }

    const parent = element.parentElement;
    if (parent) {
      const parentText = textOf(parent);
      if (parentText) {
        return parentText;
      }
    }

    return normalize(
      element.getAttribute("value") || element.getAttribute("data-value") || ""
    );
  };

  const containerLabel = (container, fallbackElement) => {
    if (container) {
      const headingText = textOf(
        container.querySelector(
          '[role="heading"], legend, .freebirdFormviewerComponentsQuestionBaseTitle'
        )
      );
      if (headingText) {
        return headingText;
      }

      const ariaLabel = container.getAttribute("aria-label");
      if (ariaLabel) {
        return normalize(ariaLabel);
      }

      const labelledBy = labeledByText(container);
      if (labelledBy) {
        return labelledBy;
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

    if (tag === "select" || role === "combobox") {
      return "select";
    }

    if (tag === "input") {
      const inputType = (element.getAttribute("type") || "text").toLowerCase();
      if (["email", "tel", "number", "date"].includes(inputType)) {
        return inputType;
      }
      if (["text", "search", "url", "password"].includes(inputType)) {
        return "text";
      }
      if (inputType === "checkbox") {
        return "checkbox";
      }
      if (inputType === "radio") {
        return "radio";
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

    const groupId = `g_${groupCounter}`;
    for (const element of group.elements) {
      element.setAttribute("data-agent-group-id", groupId);
    }

    const first = group.elements[0];
    const label = containerLabel(group.container, first);
    const options = group.elements.map((element) => optionLabel(element));
    const optionValues = group.elements.map((element) =>
      normalize(
        element.getAttribute("value") ||
          element.getAttribute("data-value") ||
          optionLabel(element)
      )
    );
    const required = group.elements.some(
      (element) =>
        Boolean(element.required) ||
        element.getAttribute("aria-required") === "true"
    );
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
      field_id: `f_${fieldCounter}`,
      selector: `[data-agent-group-id="${groupId}"]`,
      label,
      field_type: fieldType,
      required,
      options,
      option_values: optionValues,
      placeholder: null,
      name,
      input_type: group.isRadio ? "radio" : "checkbox",
      group_name: name,
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
    const fieldId = `f_${fieldCounter}`;
    element.setAttribute("data-agent-field-id", fieldId);

    const tag = element.tagName.toLowerCase();
    const inputType =
      tag === "input"
        ? (element.getAttribute("type") || "text").toLowerCase()
        : "";
    const options = [];
    const optionValues = [];

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
      required:
        Boolean(element.required) ||
        element.getAttribute("aria-required") === "true",
      options,
      option_values: optionValues,
      placeholder: element.getAttribute("placeholder"),
      name: element.getAttribute("name"),
      input_type: inputType || null,
      group_name: null,
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


# Detecta campos e metadados de formulário na página atual.
class FormDetector:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # Executa a extração e converte o resultado para os schemas da aplicação.
    async def detect(
        self,
        page: Page,
        page_snapshot: PageSnapshot | None = None,
    ) -> DetectionResult:
        snapshot = page_snapshot or await PageInspector(self.settings).inspect(page)
        raw_fields = await page.evaluate(EXTRACTION_SCRIPT)

        if not isinstance(raw_fields, list):
            raise RuntimeError("O extrator retornou um formato inesperado.")

        warnings = list(snapshot.warnings)
        fields: list[DetectedField] = []

        for raw in raw_fields:
            field_type_value = str(raw.get("field_type") or "unknown")
            try:
                field_type = FieldType(field_type_value)
            except ValueError:
                field_type = FieldType.UNKNOWN
                _append_warning(
                    warnings,
                    f"Tipo de campo desconhecido: {field_type_value}.",
                )

            field = DetectedField(
                field_id=str(raw["field_id"]),
                selector=str(raw["selector"]),
                label=str(raw.get("label") or ""),
                field_type=field_type,
                required=bool(raw.get("required")),
                options=[str(item) for item in (raw.get("options") or [])],
                option_values=[
                    str(item) for item in (raw.get("option_values") or [])
                ],
                placeholder=raw.get("placeholder") or None,
                name=raw.get("name") or None,
                input_type=raw.get("input_type") or None,
                group_name=raw.get("group_name") or None,
                visible=bool(raw.get("visible", True)),
                disabled=bool(raw.get("disabled", False)),
                readonly=bool(raw.get("readonly", False)),
            )
            fields.append(field)

        if not fields:
            _append_warning(warnings, "Nenhum campo de formulário foi detectado.")

        if any(field.input_type == "file" for field in fields):
            _append_warning(
                warnings,
                "Campos de arquivo foram detectados, mas não são suportados nesta versão.",
            )

        if any(
            field.field_type == FieldType.UNKNOWN and field.input_type != "file"
            for field in fields
        ):
            _append_warning(warnings, "Existem campos com tipo não suportado.")

        return DetectionResult(
            page=snapshot,
            fields=fields,
            warnings=warnings,
        )
