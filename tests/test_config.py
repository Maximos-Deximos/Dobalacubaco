# Testes das configurações carregadas do ambiente.

import pytest

from app.config import Settings


# Confere os valores padrão quando nenhuma variável é informada.
def test_default_settings() -> None:
    settings = Settings.from_env(env={})

    assert settings.ollama_model == "qwen3.5:4b"
    assert settings.ollama_embed_model == "bge-m3"
    assert settings.ai_provider == "ollama"
    assert settings.ai_model == "qwen3.5:4b"
    assert settings.ai_embed_provider == "ollama"
    assert settings.ai_embed_model == "bge-m3"
    assert settings.ai_api_key == ""
    assert settings.rag_chunk_chars == 1800
    assert settings.rag_chunk_overlap == 250
    assert settings.rag_top_k == 6
    assert settings.rag_embed_batch == 16
    assert settings.database_url.startswith("sqlite:///")
    assert settings.headless is False
    assert settings.sensitive_field_action == "confirm"


# Confere conversão de listas, booleanos e inteiros.
def test_lists_and_booleans() -> None:
    settings = Settings.from_env(
        env={
            "ALLOWED_DOMAINS": "Example.com, docs.google.com",
            "DENIED_DOMAINS": "bad.test",
            "ALLOW_PRIVATE_NETWORKS": "true",
            "HEADLESS": "1",
            "MAX_ACTIONS": "42",
        }
    )

    assert settings.allowed_domains == ("example.com", "docs.google.com")
    assert settings.denied_domains == ("bad.test",)
    assert settings.allow_private_networks is True
    assert settings.headless is True
    assert settings.max_actions == 42


# Rejeita valores desconhecidos para o tratamento de campos sensíveis.
def test_invalid_sensitive_action() -> None:
    with pytest.raises(ValueError):
        Settings.from_env(env={"SENSITIVE_FIELD_ACTION": "enviar"})


# Rejeita sobreposição maior ou igual ao tamanho do trecho.
def test_invalid_rag_overlap() -> None:
    with pytest.raises(ValueError):
        Settings.from_env(env={"RAG_CHUNK_CHARS": "500", "RAG_CHUNK_OVERLAP": "500"})


# Rejeita temperatura fora da faixa aceita.
def test_invalid_rag_temperature() -> None:
    with pytest.raises(ValueError):
        Settings.from_env(env={"RAG_TEMPERATURE": "3"})


# Configura um provedor externo usando a chave genérica.
def test_external_provider_settings() -> None:
    settings = Settings.from_env(
        env={
            "AI_PROVIDER": "openai",
            "AI_API_KEY": "sk-teste",
            "AI_TIMEOUT": "30",
            "AI_EMBED_PROVIDER": "none",
        }
    )

    assert settings.ai_provider == "openai"
    assert settings.ai_model == "gpt-4o-mini"
    assert settings.ai_api_key == "sk-teste"
    assert settings.ai_timeout == 30
    assert settings.ai_embed_provider == "none"
    assert settings.ai_embed_model == ""


# Aceita a variável específica do provedor como chave de API.
def test_provider_specific_api_key() -> None:
    settings = Settings.from_env(
        env={
            "AI_PROVIDER": "anthropic",
            "ANTHROPIC_API_KEY": "sk-ant-teste",
        }
    )

    assert settings.ai_model == "claude-3-5-haiku-latest"
    assert settings.ai_api_key == "sk-ant-teste"


# Rejeita provedor externo sem chave de API.
def test_external_provider_requires_api_key() -> None:
    with pytest.raises(ValueError, match="chave de API"):
        Settings.from_env(env={"AI_PROVIDER": "openai"})


# Rejeita provedor de embedding externo sem chave de API.
def test_external_embedding_requires_api_key() -> None:
    with pytest.raises(ValueError, match="chave de API"):
        Settings.from_env(env={"AI_EMBED_PROVIDER": "gemini"})


# Mantém as variáveis antigas do Ollama como valores padrão.
def test_legacy_ollama_fallback() -> None:
    settings = Settings.from_env(
        env={
            "OLLAMA_MODEL": "modelo-antigo",
            "OLLAMA_EMBED_MODEL": "embed-antigo",
            "OLLAMA_TIMEOUT": "45",
        }
    )

    assert settings.ai_model == "modelo-antigo"
    assert settings.ai_embed_model == "embed-antigo"
    assert settings.ai_timeout == 45


# Rejeita provedores desconhecidos.
def test_invalid_ai_provider() -> None:
    with pytest.raises(ValueError, match="AI_PROVIDER"):
        Settings.from_env(env={"AI_PROVIDER": "inventado"})

    with pytest.raises(ValueError, match="AI_EMBED_PROVIDER"):
        Settings.from_env(env={"AI_EMBED_PROVIDER": "inventado"})
