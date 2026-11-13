# Armazenamento local dos arquivos originais e textos extraídos.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings

# Extensões permitidas para os arquivos originais.
ALLOWED_EXTENSIONS = {".html", ".htm", ".pdf"}


# Erro lançado quando o armazenamento não pode ser preparado.
class StorageError(RuntimeError):
    pass


# Salva originais e textos extraídos dentro do workspace.
class SourceStorage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # Prepara e devolve o diretório da fonte.
    def source_dir(self, workspace_id: int, source_id: int) -> Path:
        if workspace_id < 1 or source_id < 1:
            raise StorageError("Identificadores de workspace e fonte inválidos.")

        path = (
            self.settings.data_dir
            / "workspaces"
            / str(workspace_id)
            / "sources"
            / str(source_id)
        ).resolve()
        data_root = self.settings.data_dir.resolve()
        if data_root not in path.parents:
            raise StorageError("Caminho de armazenamento inválido.")
        return path

    # Persiste o original, o texto extraído e os metadados.
    def save(
        self,
        *,
        workspace_id: int,
        source_id: int,
        content: bytes,
        extension: str,
        text: str,
        metadata: dict[str, Any],
    ) -> str:
        directory = self.source_dir(workspace_id, source_id)
        directory.mkdir(parents=True, exist_ok=True)

        safe_extension = extension.lower()
        if safe_extension not in ALLOWED_EXTENSIONS:
            safe_extension = ".bin"

        raw_path = directory / f"original{safe_extension}"
        text_path = directory / "extracted.txt"
        metadata_path = directory / "metadata.json"

        try:
            self._atomic_write(raw_path, content)
            self._atomic_write(text_path, text.encode("utf-8"))
            self._atomic_write(
                metadata_path,
                json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
            )
        except OSError as exc:
            raise StorageError(f"Falha ao salvar a fonte: {exc}") from exc

        return str(raw_path)

    # Escreve em arquivo temporário e renomeia de forma atômica.
    def _atomic_write(self, path: Path, content: bytes) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
