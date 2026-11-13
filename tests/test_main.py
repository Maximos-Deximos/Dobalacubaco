# Testes das verificações de ambiente do comando doctor.

import httpx
import respx

from app.main import _check_ollama

BASE_URL = "http://127.0.0.1:11434"


# Trata a tag implícita ":latest" como o mesmo modelo instalado.
@respx.mock
def test_check_ollama_accepts_latest_tag() -> None:
    respx.get(f"{BASE_URL}/api/tags").mock(
        return_value=httpx.Response(
            200,
            json={"models": [{"name": "qwen3.5:4b"}, {"name": "bge-m3:latest"}]},
        )
    )

    chat_ok, _, embed_ok, _ = _check_ollama(
        BASE_URL,
        5,
        "qwen3.5:4b",
        "bge-m3",
    )

    assert chat_ok is True
    assert embed_ok is True


# Sinaliza modelos ausentes com a instrução de instalação.
@respx.mock
def test_check_ollama_reports_missing_model() -> None:
    respx.get(f"{BASE_URL}/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "qwen3.5:4b"}]})
    )

    _, _, embed_ok, embed_detail = _check_ollama(
        BASE_URL,
        5,
        "qwen3.5:4b",
        "bge-m3",
    )

    assert embed_ok is False
    assert "ollama pull bge-m3" in embed_detail
