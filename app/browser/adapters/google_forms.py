# Adaptador de detecção para formulários públicos do Google Forms.

from __future__ import annotations

from urllib.parse import urlparse

from playwright.async_api import Frame
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

# Extrai perguntas, opções e metadados usando a estrutura semântica do Google Forms.
GOOGLE_FORMS_SCRIPT = r"""
(args) => {
  const prefix = (args && args.prefix) || "";
  const normalize = (value) => (value || "").replace(/\s+/g, " ").trim().slice(0, 500);
  const cleanLabel = (value) => normalize(value).replace(/\s*\*+\s*$/g, "").trim();
  const genericAnswerLabel = /^(sua resposta|your answer|resposta|answer)$/i;
  const controlSelector = [
    "input",
    "textarea",
    "select",
    '[contenteditable="true"]',
    '[role="textbox"]',
    '[role="combobox"]',
    '[role="listbox"]',
    '[role="radio"]',
    '[role="checkbox"]',
    '[role="option"]'
  ].join(",");

  const textOf = (element) => normalize(
    element ? (element.innerText || element.textContent || "") : ""
  );

  const isVisible = (element) => {
    if (!element) {
      return false;
    }
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

  const labelledByText = (element) => {
    if (!element) {
      return "";
    }
    const ids = element.getAttribute("aria-labelledby");
    if (!ids) {
      return "";
    }
    return cleanLabel(
      ids
        .split(/\s+/)
        .map((id) => document.getElementById(id))
        .filter(Boolean)
        .map((node) => textOf(node))
        .join(" ")
    );
  };

  const describedText = (element) => {
    if (!element) {
      return "";
    }
    const ids = (element.getAttribute("aria-describedby") || "")
      .split(/\s+/)
      .filter(Boolean);
    return cleanLabel(
      Array.from(new Set(ids))
        .map((id) => document.getElementById(id))
        .filter(Boolean)
        .map((node) => textOf(node))
        .filter(Boolean)
        .join(" ")
    );
  };

  const requiredInfo = (container, control) => {
    const group = control ? control.closest(
      '[role="radiogroup"], [role="group"], fieldset, [role="grid"], table, [role="listbox"]'
    ) : null;

    for (const node of [control, group, container]) {
      if (!node) {
        continue;
      }
      if (node.required || node.getAttribute("aria-required") === "true") {
        return { required: true, source: "native" };
      }
      if (node.getAttribute("data-required") === "true") {
        return { required: true, source: "data-required" };
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

  const mark = (element, attribute, value) => {
    if (element) {
      element.setAttribute(attribute, value);
    }
    return element;
  };

  const questionTitle = (container, fallback) => {
    const labelledBy = labelledByText(container);
    if (labelledBy) {
      return labelledBy;
    }

    const heading = container.querySelector(
      '[role="heading"], .freebirdFormviewerComponentsQuestionBaseTitle'
    );
    const headingText = cleanLabel(textOf(heading));
    if (headingText) {
      return headingText;
    }

    if (fallback) {
      const fallbackLabel = labelledByText(fallback);
      if (fallbackLabel) {
        return fallbackLabel;
      }
      const ariaLabel = cleanLabel(fallback.getAttribute("aria-label"));
      if (ariaLabel && !genericAnswerLabel.test(ariaLabel)) {
        return ariaLabel;
      }
    }

    return "";
  };

  const optionLabel = (element) => {
    if (!element) {
      return "";
    }

    if (element.labels && element.labels.length > 0) {
      const labelText = cleanLabel(
        element.labels[0].innerText || element.labels[0].textContent
      );
      if (labelText) {
        return labelText;
      }
    }

    const ariaLabel = cleanLabel(element.getAttribute("aria-label"));
    if (ariaLabel && !genericAnswerLabel.test(ariaLabel)) {
      return ariaLabel;
    }

    const text = cleanLabel(element.innerText || element.textContent);
    if (text) {
      return text;
    }

    return cleanLabel(
      element.getAttribute("value") || element.getAttribute("data-value") || ""
    );
  };

  const optionValue = (element, label) => cleanLabel(
    element.getAttribute("data-value") ||
      element.getAttribute("value") ||
      label
  );

  const optionDescriptor = (element, fieldId, index) => {
    const label = optionLabel(element);
    const optionId = `${fieldId}_o${index}`;
    mark(element, "data-agent-option-id", optionId);
    return {
      label,
      value: optionValue(element, label),
      selector: `[data-agent-option-id="${optionId}"]`,
      disabled:
        Boolean(element.disabled) ||
        element.getAttribute("aria-disabled") === "true"
    };
  };

  const uniqueElements = (elements) => Array.from(new Set(elements));

  const nativeChoiceElements = (container, kind) => Array.from(
    container.querySelectorAll(`input[type="${kind}"]`)
  ).filter((element) => (element.getAttribute("type") || "").toLowerCase() === kind);

  const ariaChoiceElements = (container, role) => Array.from(
    container.querySelectorAll(`[role="${role}"]`)
  );

  const gridRows = (container) => {
    const grid = container.querySelector('table, [role="grid"]');
    if (!grid) {
      return null;
    }

    let rows = Array.from(grid.querySelectorAll('[role="row"]'));
    if (!rows.length) {
      rows = Array.from(grid.querySelectorAll("tr"));
    }

    rows = rows.filter((row) => {
      const cells = Array.from(row.querySelectorAll("td, th"));
      const hasChoices = Boolean(
        row.querySelector(
          'input[type="radio"], input[type="checkbox"], [role="radio"], [role="checkbox"]'
        )
      );
      return cells.length > 1 && hasChoices;
    });

    if (rows.length < 2) {
      return null;
    }

    return { grid, rows };
  };

  const columnLabels = (grid) => {
    const headerCells = Array.from(
      grid.querySelectorAll('thead th, [role="columnheader"]')
    ).map((cell) => cleanLabel(textOf(cell))).filter(Boolean);

    if (headerCells.length) {
      return headerCells;
    }

    const firstRow = grid.querySelector("tr");
    if (!firstRow) {
      return [];
    }

    return Array.from(firstRow.querySelectorAll("th"))
      .map((cell) => cleanLabel(textOf(cell)))
      .filter(Boolean);
  };

  const questionContainers = () => {
    let candidates = Array.from(document.querySelectorAll(
      ".freebirdFormviewerComponentsQuestionBaseRoot"
    ));

    if (!candidates.length) {
      candidates = Array.from(document.querySelectorAll('[role="listitem"]'))
        .filter((element) => element.closest('[role="listitem"]') === element);
    }

    return candidates.filter((container) => {
      const hasHeading = Boolean(container.querySelector('[role="heading"]'));
      const hasControl = Boolean(container.querySelector(controlSelector));
      return hasHeading && hasControl;
    });
  };

  const sectionTitle = () => {
    const outsideQuestions = Array.from(
      document.querySelectorAll('[role="heading"]')
    ).filter(
      (heading) => !heading.closest(
        '[role="listitem"], .freebirdFormviewerComponentsQuestionBaseRoot'
      )
    );
    return cleanLabel(textOf(outsideQuestions[outsideQuestions.length - 1]));
  };

  const pageHasNext = () => {
    const buttons = Array.from(
      document.querySelectorAll('button, [role="button"]')
    ).map((element) => cleanLabel(textOf(element))).filter(Boolean);

    return buttons.some((label) =>
      /\b(next|próxima|proxima|continuar|avançar|avancar|seguir|continue|siguiente)\b/i.test(
        label
      )
    );
  };

  const formTitle = () => cleanLabel(
    document.title.replace(/\s*-\s*Google Forms\s*$/i, "")
  );

  const containers = questionContainers();
  const fields = [];
  const warnings = [];

  for (const container of containers) {
    const fieldNumber = fields.length + 1;
    const fieldId = `${prefix}gf_${fieldNumber}`;
    const controls = Array.from(container.querySelectorAll(controlSelector))
      .filter((element) => {
        const tag = element.tagName.toLowerCase();
        const inputType = (element.getAttribute("type") || "").toLowerCase();
        if (tag === "input" && ["hidden", "submit", "button", "reset", "image"].includes(inputType)) {
          return false;
        }
        return !element.closest('[role="option"]');
      });
    const firstControl = controls[0] || null;
    const title = questionTitle(container, firstControl);
    const requiredState = requiredInfo(container, firstControl);
    const helpText = describedText(firstControl) || describedText(container);
    const base = {
      field_id: fieldId,
      selector: "",
      label: title || "Pergunta sem título",
      field_type: "unknown",
      required: requiredState.required,
      required_source: requiredState.source,
      options: [],
      option_values: [],
      option_details: [],
      subfields: [],
      placeholder: firstControl ? firstControl.getAttribute("placeholder") : null,
      name: firstControl ? firstControl.getAttribute("name") : null,
      input_type: firstControl ? (firstControl.getAttribute("type") || null) : null,
      group_name: null,
      description: helpText,
      help_text: helpText,
      section_title: "",
      question_number: String(fieldNumber),
      constraints: firstControl ? constraintsFor(firstControl) : {},
      adapter: "google_forms",
      frame_url: null,
      visible: isVisible(container) || controls.some((control) => isVisible(control)),
      disabled: controls.length > 0 && controls.every(
        (control) =>
          Boolean(control.disabled) ||
          control.getAttribute("aria-disabled") === "true"
      ),
      readonly: controls.length > 0 && controls.every(
        (control) =>
          Boolean(control.readOnly) ||
          control.getAttribute("aria-readonly") === "true"
      )
    };

    const fileControl = container.querySelector('input[type="file"]');
    if (fileControl) {
      mark(container, "data-agent-field-id", fieldId);
      fields.push({
        ...base,
        selector: `[data-agent-field-id="${fieldId}"]`,
        field_type: "file",
        input_type: "file",
        required: requiredInfo(container, fileControl).required,
        required_source: requiredInfo(container, fileControl).source
      });
      continue;
    }

    const grid = gridRows(container);
    if (grid) {
      const columns = columnLabels(grid.grid);
      const columnOptions = columns.map((label, index) => ({
        label,
        value: label,
        selector: null,
        disabled: false
      }));
      const subfields = [];

      for (const [rowIndex, row] of grid.rows.entries()) {
        const rowLabelElement = row.querySelector(
          'th, [role="rowheader"]'
        );
        const rowLabel = cleanLabel(textOf(rowLabelElement))
          || `Linha ${rowIndex + 1}`;
        const rowId = `${fieldId}_r${rowIndex + 1}`;
        mark(row, "data-agent-subfield-id", rowId);
        const rowChoices = uniqueElements([
          ...ariaChoiceElements(row, "radio"),
          ...ariaChoiceElements(row, "checkbox"),
          ...nativeChoiceElements(row, "radio"),
          ...nativeChoiceElements(row, "checkbox")
        ]);
        const kind = row.querySelector('input[type="checkbox"], [role="checkbox"]')
          ? "checkbox"
          : "radio";
        const rowOptions = rowChoices.map((choice, index) => {
          const label = optionLabel(choice);
          const fallbackLabel = columns[index] || label;
          const optionId = `${rowId}_o${index + 1}`;
          mark(choice, "data-agent-option-id", optionId);
          return {
            label: fallbackLabel,
            value: optionValue(choice, fallbackLabel),
            selector: `[data-agent-option-id="${optionId}"]`,
            disabled:
              Boolean(choice.disabled) ||
              choice.getAttribute("aria-disabled") === "true"
          };
        });
        subfields.push({
          subfield_id: rowId,
          label: rowLabel,
          field_type: kind,
          selector: `[data-agent-subfield-id="${rowId}"]`,
          required: requiredState.required,
          options: rowOptions
        });
      }

      mark(container, "data-agent-field-id", fieldId);
      fields.push({
        ...base,
        selector: `[data-agent-field-id="${fieldId}"]`,
        field_type: "grid",
        options: columns,
        option_values: columns,
        option_details: columnOptions,
        subfields,
        input_type: "grid"
      });
      if (!columns.length) {
        warnings.push("Grid sem cabeçalhos de coluna detectados.");
      }
      continue;
    }

    const dateControls = controls.filter((control) => {
      const inputType = (control.getAttribute("type") || "").toLowerCase();
      if (["date", "datetime-local"].includes(inputType)) {
        return true;
      }
      return /\b(dd|dia|day|mm|mês|mes|month|yyyy|ano|year)\b/i.test(
        cleanLabel(control.getAttribute("aria-label") || "")
      );
    });
    const timeControls = controls.filter((control) => {
      const inputType = (control.getAttribute("type") || "").toLowerCase();
      if (inputType === "time") {
        return true;
      }
      return /\b(hh|mm|ss|hora|hour|min|minuto|minute|seg|segundo|second|am|pm)\b/i.test(
        cleanLabel(control.getAttribute("aria-label") || "")
      );
    });

    const dateParts = dateControls.length > 1
      ? dateControls
      : (dateControls.length === 1 && ["date", "datetime-local"].includes(
        (dateControls[0].getAttribute("type") || "").toLowerCase()
      ) ? dateControls : []);
    const timeParts = timeControls.length > 1
      ? timeControls
      : (timeControls.length === 1 && (timeControls[0].getAttribute("type") || "").toLowerCase() === "time"
        ? timeControls : []);

    if (dateParts.length || timeParts.length) {
      const isDate = dateParts.length > 0;
      const parts = isDate ? dateParts : timeParts;
      const subfields = parts.map((control, index) => {
        const partId = `${fieldId}_s${index + 1}`;
        mark(control, "data-agent-subfield-id", partId);
        return {
          subfield_id: partId,
          label: cleanLabel(control.getAttribute("aria-label") || "") || `Parte ${index + 1}`,
          field_type: isDate ? "date" : "time",
          selector: `[data-agent-subfield-id="${partId}"]`,
          required: requiredInfo(container, control).required,
          options: []
        };
      });
      mark(container, "data-agent-field-id", fieldId);
      fields.push({
        ...base,
        selector: `[data-agent-field-id="${fieldId}"]`,
        field_type: isDate ? "date" : "time",
        input_type: isDate ? "date" : "time",
        subfields,
        constraints: constraintsFor(parts[0])
      });
      continue;
    }

    const listbox = controls.find((control) => {
      const tag = control.tagName.toLowerCase();
      const role = (control.getAttribute("role") || "").toLowerCase();
      return tag === "select" || role === "listbox" || role === "combobox";
    });

    if (listbox) {
      let optionElements = Array.from(listbox.querySelectorAll('[role="option"]'));
      if (listbox.tagName.toLowerCase() === "select") {
        optionElements = Array.from(listbox.options);
      }
      if (!optionElements.length) {
        const popup = container.querySelector('[role="listbox"]');
        if (popup) {
          optionElements = Array.from(popup.querySelectorAll('[role="option"]'));
        }
      }

      const optionDetails = optionElements.map((option, index) =>
        optionDescriptor(option, fieldId, index + 1)
      ).filter((option) => option.label);
      mark(container, "data-agent-field-id", fieldId);
      fields.push({
        ...base,
        selector: `[data-agent-field-id="${fieldId}"]`,
        field_type: "select",
        input_type: "select",
        options: optionDetails.map((option) => option.label),
        option_values: optionDetails.map((option) => option.value),
        option_details: optionDetails,
        required: requiredInfo(container, listbox).required,
        required_source: requiredInfo(container, listbox).source
      });
      if (!optionDetails.length) {
        warnings.push(
          `O campo '${base.label}' parece ser um dropdown sem opções visíveis.`
        );
      }
      continue;
    }

    const radioElements = uniqueElements([
      ...ariaChoiceElements(container, "radio"),
      ...nativeChoiceElements(container, "radio")
    ]);
    const checkboxElements = uniqueElements([
      ...ariaChoiceElements(container, "checkbox"),
      ...nativeChoiceElements(container, "checkbox")
    ]);
    const groupElements = radioElements.length ? radioElements : checkboxElements;

    if (groupElements.length) {
      const isRadio = radioElements.length > 0;
      const kind = isRadio ? "radio" : "checkbox";
      const optionDetails = groupElements.map((element, index) =>
        optionDescriptor(element, fieldId, index + 1)
      ).filter((option) => option.label);
      const consent = !isRadio &&
        groupElements.length === 1 &&
        /(concordo|aceito|consent|termos|privacidade|autorizo|agree)/i.test(
          `${base.label} ${optionDetails[0] ? optionDetails[0].label : ""}`
        );
      const required = requiredInfo(container, groupElements[0]).required;
      for (const element of groupElements) {
        mark(element, "data-agent-group-id", fieldId);
      }
      mark(container, "data-agent-field-id", fieldId);
      fields.push({
        ...base,
        selector: `[data-agent-field-id="${fieldId}"]`,
        field_type: consent ? "consent" : kind,
        required,
        required_source: requiredInfo(container, groupElements[0]).source,
        options: optionDetails.map((option) => option.label),
        option_values: optionDetails.map((option) => option.value),
        option_details: optionDetails,
        input_type: kind,
        group_name: groupElements
          .map((element) => element.getAttribute("name") || "")
          .find(Boolean) || null
      });
      continue;
    }

    const textControls = controls.filter((control) => {
      const tag = control.tagName.toLowerCase();
      const role = (control.getAttribute("role") || "").toLowerCase();
      return tag === "textarea" || tag === "input" ||
        role === "textbox" || control.isContentEditable;
    });

    if (textControls.length) {
      const first = textControls[0];
      const tag = first.tagName.toLowerCase();
      const inputType = (first.getAttribute("type") || "text").toLowerCase();
      let fieldType = "text";
      if (tag === "textarea") {
        fieldType = "textarea";
      } else if (["email", "tel", "number", "url", "date", "time"].includes(inputType)) {
        fieldType = inputType;
      } else if (inputType === "file") {
        fieldType = "file";
      }

      if (textControls.length === 1) {
        mark(first, "data-agent-field-id", fieldId);
        fields.push({
          ...base,
          selector: `[data-agent-field-id="${fieldId}"]`,
          field_type: fieldType,
          input_type: inputType,
          required: requiredInfo(container, first).required,
          required_source: requiredInfo(container, first).source,
          placeholder: first.getAttribute("placeholder"),
          name: first.getAttribute("name"),
          constraints: constraintsFor(first)
        });
      } else {
        const subfields = textControls.map((control, index) => {
          const partId = `${fieldId}_s${index + 1}`;
          mark(control, "data-agent-subfield-id", partId);
          return {
            subfield_id: partId,
            label: cleanLabel(control.getAttribute("aria-label") || "") || `Parte ${index + 1}`,
            field_type: (control.getAttribute("type") || "text").toLowerCase(),
            selector: `[data-agent-subfield-id="${partId}"]`,
            required: requiredInfo(container, control).required,
            options: []
          };
        });
        mark(container, "data-agent-field-id", fieldId);
        fields.push({
          ...base,
          selector: `[data-agent-field-id="${fieldId}"]`,
          field_type: "text",
          input_type: "text",
          subfields,
          constraints: constraintsFor(first)
        });
      }
      continue;
    }

    if (/(upload|arquivo|anexo|file)/i.test(base.label)) {
      mark(container, "data-agent-field-id", fieldId);
      fields.push({
        ...base,
        selector: `[data-agent-field-id="${fieldId}"]`,
        field_type: "file",
        input_type: "file"
      });
      continue;
    }

    warnings.push(`Pergunta sem controle reconhecido: ${base.label}`);
  }

  const hasNext = pageHasNext();
  if (hasNext) {
    warnings.push(
      "O formulário possui mais de uma seção; apenas a página atual foi inspecionada."
    );
  }

  return {
    fields,
    metadata: {
      form_title: formTitle(),
      form_description: "",
      section_title: sectionTitle(),
      section_description: "",
      page_index: 1,
      has_next: hasNext,
      is_google_form: true,
      warnings
    }
  };
}
"""


# Verifica se a URL pertence ao domínio do Google Forms.
def is_google_forms_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if hostname == "docs.google.com":
        return parsed.path.startswith("/forms/")
    return hostname in {"forms.gle", "forms.google.com"}


# Adaptador que extrai campos sem depender das classes geradas do Google.
class GoogleFormsAdapter:
    name = "google_forms"

    @staticmethod
    def matches(url: str) -> bool:
        return is_google_forms_url(url)

    # Executa o extrator no frame informado e devolve o payload bruto.
    async def extract(self, frame: Frame, prefix: str) -> dict:
        try:
            await frame.wait_for_selector(
                '[role="listitem"], .freebirdFormviewerComponentsQuestionBaseRoot',
                state="attached",
                timeout=5_000,
            )
        except PlaywrightTimeoutError:
            pass

        payload = await frame.evaluate(
            GOOGLE_FORMS_SCRIPT,
            {"prefix": prefix},
        )

        if not isinstance(payload, dict):
            raise TypeError("O adaptador do Google Forms retornou um formato inválido.")

        if not isinstance(payload.get("fields"), list):
            raise TypeError(
                "O adaptador do Google Forms não retornou uma lista de campos."
            )

        if not isinstance(payload.get("metadata"), dict):
            payload["metadata"] = {}

        return payload
