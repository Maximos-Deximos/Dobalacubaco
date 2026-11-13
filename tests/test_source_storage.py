# Testes do armazenamento local de fontes.

from pathlib import Path

import pytest

from app.config import Settings
from app.ingestion.storage import SourceStorage, StorageError


# Salva original, texto e metadados no diretório do workspace.
def test_save_source_files(tmp_path) -> None:
    settings = Settings.from_env(env={"DATA_DIR": str(tmp_path)})
    storage = SourceStorage(settings)

    raw_path = storage.save(
        workspace_id=1,
        source_id=2,
        content=b"conteudo",
        extension=".pdf",
        text="texto extraído",
        metadata={"tipo": "teste"},
    )

    directory = tmp_path / "workspaces" / "1" / "sources" / "2"
    assert Path(raw_path) == directory / "original.pdf"
    assert (directory / "original.pdf").read_bytes() == b"conteudo"
    assert (directory / "extracted.txt").read_text(encoding="utf-8") == "texto extraído"
    assert '"tipo": "teste"' in (directory / "metadata.json").read_text(encoding="utf-8")


# Normaliza extensões desconhecidas.
def test_unknown_extension_uses_bin(tmp_path) -> None:
    settings = Settings.from_env(env={"DATA_DIR": str(tmp_path)})
    storage = SourceStorage(settings)

    raw_path = storage.save(
        workspace_id=1,
        source_id=1,
        content=b"x",
        extension=".exe",
        text="",
        metadata={},
    )

    assert raw_path.endswith("original.bin")


# Rejeita identificadores inválidos.
def test_rejects_invalid_ids(tmp_path) -> None:
    settings = Settings.from_env(env={"DATA_DIR": str(tmp_path)})
    storage = SourceStorage(settings)

    with pytest.raises(StorageError):
        storage.source_dir(0, 1)
