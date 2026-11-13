# Rótulos em português usados por todas as telas da TUI.

from __future__ import annotations

WORKSPACE_STATUS_LABELS = {
    "active": "Ativa",
    "archived": "Arquivada",
}

SOURCE_KIND_LABELS = {
    "web_page": "Página web",
    "web_pdf": "PDF da web",
    "uploaded_html": "HTML local",
    "uploaded_pdf": "PDF local",
}

SOURCE_STATUS_LABELS = {
    "pending": "Pendente",
    "fetching": "Baixando",
    "extracting": "Extraindo",
    "ready": "Pronta",
    "failed": "Falhou",
    "needs_ocr": "Precisa de OCR",
}

PROPOSAL_STATUS_LABELS = {
    "draft": "Rascunho",
    "in_review": "Em revisão",
    "completed": "Concluída",
    "archived": "Arquivada",
}

SECTION_STATUS_LABELS = {
    "empty": "Vazia",
    "draft": "Rascunho",
    "in_review": "Em revisão",
    "approved": "Aprovada",
}

RETRIEVAL_MODE_LABELS = {
    "semantic": "Semântica",
    "lexical": "Lexical",
}

FIELD_TYPE_LABELS = {
    "text": "Texto",
    "email": "E-mail",
    "tel": "Telefone",
    "number": "Número",
    "url": "URL",
    "date": "Data",
    "time": "Hora",
    "textarea": "Texto longo",
    "select": "Seleção",
    "radio": "Escolha única",
    "checkbox": "Caixa de seleção",
    "consent": "Consentimento",
    "file": "Arquivo",
    "grid": "Grade",
    "unknown": "Desconhecido",
}


# Traduz um valor de enum ou texto para o rótulo correspondente.
def label_for(labels: dict[str, str], value: object) -> str:
    key = str(getattr(value, "value", value))
    return labels.get(key, key)


PDF_SESSION_STATUS_LABELS = {
    "draft": "Rascunho",
    "suggested": "Sugerida",
    "reviewing": "Em revisão",
    "ready": "Pronta",
    "filled": "Preenchida",
    "failed": "Falhou",
}

PDF_FIELD_STATUS_LABELS = {
    "pending": "Pendente",
    "suggested": "Sugerido",
    "edited": "Editado",
    "approved": "Aprovado",
    "skipped": "Ignorado",
    "filled": "Preenchido",
    "failed": "Falhou",
}

PDF_FIELD_TYPE_LABELS = {
    "text": "Texto",
    "textarea": "Texto longo",
    "checkbox": "Caixa",
    "radio": "Escolha",
    "choice": "Seleção",
    "signature": "Assinatura",
    "unknown": "Desconhecido",
}

PDF_SUGGESTION_SOURCE_LABELS = {
    "profile": "Perfil",
    "vector": "Memória vetorial",
    "ai": "IA",
    "manual": "Manual",
}
