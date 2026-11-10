# Testes das configurações carregadas do ambiente.

import pytest

from app.config import Settings


# Confere os valores padrão quando nenhuma variável é informada.
def test_default_settings() -> None:
    settings = Settings.from_env(env={})

    assert settings.ollama_model == "qwen3.5:4b"
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
