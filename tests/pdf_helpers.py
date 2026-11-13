# Helpers compartilhados pelos testes de formulários PDF.

from __future__ import annotations

import json
import re
from pathlib import Path

from app.application.source_service import SourceIngestionService
from app.application.workspace_service import WorkspaceService
from app.schemas.source import Source

PDF_FIXTURE = Path(__file__).parent / "fixtures" / "ingestion" / "acroform_sample.pdf"

FIELD_VALUES = {
    "full_name": "Fulano de Tal",
    "email": "fulano@example.com",
    "city": "Recife",
    "agree": "Yes",
    "gender": "F",
}


# Cria um workspace e ingere o PDF de teste.
def create_pdf_source(name: str = "Workspace PDF") -> tuple[int, Source]:
    workspace = WorkspaceService().create(name, "Teste de PDF")
    ingestion = SourceIngestionService().add_file(workspace.id, PDF_FIXTURE)
    return workspace.id, ingestion.source


# Cliente falso de embeddings e chat para exercitar o fluxo sem Ollama.
class FakePdfClient:
    def __init__(self) -> None:
        self.embed_calls = 0
        self.chat_calls = 0
        self.chat_payloads: list[list[dict]] = []

    # Gera vetores determinísticos por assunto do campo.
    def embed(self, _model: str, texts: list[str]) -> list[list[float]]:
        self.embed_calls += 1
        return [self._vector(text) for text in texts]

    # Responde com sugestões apenas para os campos enviados no lote.
    def chat(self, _model: str, messages: list, **_kwargs) -> str:
        self.chat_calls += 1
        user_content = str(messages[-1].content)
        marker = "Campos a preencher (JSON):\n"
        raw_fields = user_content.split(marker, 1)[1].split("\n\n", 1)[0]
        fields = json.loads(raw_fields)
        self.chat_payloads.append(fields)
        suggestions = []
        for field in fields:
            name = field["field_name"]
            if name not in FIELD_VALUES:
                continue
            suggestions.append(
                {
                    "field_name": name,
                    "value": FIELD_VALUES[name],
                    "confidence": 0.81,
                    "rationale": f"Valor sugerido para {name}.",
                }
            )
        return json.dumps({"suggestions": suggestions})

    # Converte texto em vetor normalizado de quatro dimensões.
    def _vector(self, text: str) -> list[float]:
        low = text.lower()
        if re.search(r"nome", low):
            return [1.0, 0.0, 0.0, 0.0]
        if re.search(r"e-?mail", low):
            return [0.0, 1.0, 0.0, 0.0]
        if re.search(r"cidade", low):
            return [0.0, 0.0, 1.0, 0.0]
        if re.search(r"aceito", low):
            return [0.0, 0.0, 0.0, 1.0]
        if re.search(r"gender|genero", low):
            return [0.7, 0.7, 0.0, 0.0]
        return [0.1, 0.1, 0.1, 0.1]
