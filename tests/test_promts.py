# Testes da montagem de mensagens enviadas ao agente.

from app.ai.promts import SYSTEM_CHAT_PROMPT_NO_SOURCES, build_chat_messages


# Usa o prompt geral quando não há trechos recuperados.
def test_build_messages_without_hits_uses_general_prompt() -> None:
    messages = build_chat_messages("Como estruturar a proposta?", [])

    assert messages[0].role == "system"
    assert messages[0].content == SYSTEM_CHAT_PROMPT_NO_SOURCES
    assert "Fontes disponíveis" not in messages[-1].content
    assert "orientação geral" in messages[-1].content
    assert "sem citar fontes" in messages[-1].content
