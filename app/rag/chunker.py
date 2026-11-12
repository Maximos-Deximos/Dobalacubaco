# Divisão do conteúdo extraído em trechos pesquisáveis.

from __future__ import annotations

import hashlib

from app.schemas.rag import ChunkDraft
from app.schemas.source import ExtractedSegment, SourceSnapshot


# Divide segmentos preservando página, seção e deslocamentos originais.
class Chunker:
    def __init__(self, chunk_chars: int = 1800, overlap: int = 250) -> None:
        if chunk_chars < 100:
            raise ValueError("O tamanho do trecho deve ser pelo menos 100.")
        if overlap < 0 or overlap >= chunk_chars:
            raise ValueError("A sobreposição deve ser menor que o tamanho do trecho.")
        self.chunk_chars = chunk_chars
        self.overlap = overlap

    # Produz os trechos de um snapshot completo.
    def chunk(self, snapshot: SourceSnapshot) -> list[ChunkDraft]:
        segments = snapshot.segments
        if not segments and snapshot.content_text.strip():
            title = str(snapshot.metadata.get("title") or "Conteúdo principal")
            segments = [
                ExtractedSegment(
                    kind="section",
                    index=1,
                    title=title,
                    text=snapshot.content_text,
                    start_offset=0,
                    end_offset=len(snapshot.content_text),
                )
            ]

        drafts: list[ChunkDraft] = []
        for segment in segments:
            text = segment.text
            if not text.strip():
                continue

            for local_start, local_end in self._windows(text):
                raw = text[local_start:local_end]
                left_trim = len(raw) - len(raw.lstrip())
                right_trim = len(raw) - len(raw.rstrip())
                chunk_text = raw.strip()
                if not chunk_text:
                    continue

                char_start = segment.start_offset + local_start + left_trim
                char_end = segment.start_offset + local_end - right_trim
                chunk_hash = hashlib.sha256(
                    f"{segment.kind}|{segment.index}|{chunk_text}".encode()
                ).hexdigest()
                drafts.append(
                    ChunkDraft(
                        chunk_index=len(drafts),
                        text=chunk_text,
                        char_start=char_start,
                        char_end=char_end,
                        page_number=(
                            segment.index if segment.kind == "page" else None
                        ),
                        section_title=(
                            "" if segment.kind == "page" else segment.title
                        ),
                        chunk_hash=chunk_hash,
                    )
                )

        return drafts

    # Calcula janelas com sobreposição e quebras naturais de texto.
    def _windows(self, text: str) -> list[tuple[int, int]]:
        windows: list[tuple[int, int]] = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = min(start + self.chunk_chars, text_length)
            if end < text_length:
                end = self._natural_break(text, start, end)

            if end <= start:
                end = min(start + self.chunk_chars, text_length)

            windows.append((start, end))
            if end >= text_length:
                break

            next_start = max(start + 1, end - self.overlap)
            if next_start <= start:
                next_start = end
            start = next_start

        return windows

    # Procura a última quebra natural dentro da segunda metade da janela.
    def _natural_break(self, text: str, start: int, end: int) -> int:
        search_from = start + max(1, self.chunk_chars // 2)
        window = text[search_from:end]

        for delimiter in ("\n\n", "\n", ". ", "; ", ", ", " "):
            position = window.rfind(delimiter)
            if position >= 0:
                candidate = search_from + position + len(delimiter)
                if candidate > start:
                    return candidate

        return end
