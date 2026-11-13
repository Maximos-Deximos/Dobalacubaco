# Testes do download HTTP e das proteções de segurança.

import socket
from dataclasses import replace
from urllib.parse import urlparse

import httpx
import pytest
import respx

from app.config import Settings
from app.ingestion.fetcher import FetchError, HttpSourceFetcher
from app.security.url_policy import UrlPolicy, UrlPolicyError

PUBLIC_IP = "93.184.216.34"


# Cria uma política com DNS simulado por host.
def make_policy(settings: Settings, address_by_host: dict[str, str] | None = None) -> UrlPolicy:
    mapping = address_by_host or {}

    def resolver(hostname, port, **_kwargs):
        address = mapping.get(hostname.lower(), PUBLIC_IP)
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (address, port),
            )
        ]

    return UrlPolicy(settings, resolver=resolver)


# Cria o fetcher com uma política de teste.
def make_fetcher(
    *,
    max_source_bytes: int = 20_971_520,
    max_redirects: int = 5,
    address_by_host: dict[str, str] | None = None,
) -> HttpSourceFetcher:
    settings = replace(
        Settings.from_env(env={}),
        max_source_bytes=max_source_bytes,
        max_redirects=max_redirects,
    )
    return HttpSourceFetcher(settings, policy=make_policy(settings, address_by_host))


# Baixa HTML público.
@respx.mock
def test_fetch_html() -> None:
    respx.get("https://example.com/edital").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"<html><body>Edital</body></html>",
        )
    )

    resource = make_fetcher().fetch("https://example.com/edital")

    assert resource.content_type == "text/html"
    assert resource.final_url == "https://example.com/edital"
    assert resource.status_code == 200
    assert b"Edital" in resource.content


# Baixa PDF mesmo quando o servidor usa octet-stream.
@respx.mock
def test_fetch_pdf_by_magic_bytes() -> None:
    respx.get("https://example.com/edital.pdf").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "application/octet-stream"},
            content=b"%PDF-1.4\nconteudo",
        )
    )

    resource = make_fetcher().fetch("https://example.com/edital.pdf")

    assert resource.content_type == "application/pdf"


# Rejeita resposta HTTP de erro.
@respx.mock
def test_fetch_rejects_http_error() -> None:
    respx.get("https://example.com/edital").mock(
        return_value=httpx.Response(404, content=b"not found")
    )

    with pytest.raises(FetchError):
        make_fetcher().fetch("https://example.com/edital")


# Impede download acima do limite.
@respx.mock
def test_fetch_rejects_large_content() -> None:
    respx.get("https://example.com/edital").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"x" * 20,
        )
    )

    with pytest.raises(FetchError):
        make_fetcher(max_source_bytes=10).fetch("https://example.com/edital")


# Rejeita tipos de conteúdo não suportados.
@respx.mock
def test_fetch_rejects_unsupported_content_type() -> None:
    respx.get("https://example.com/imagem").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=b"\x89PNG\r\n",
        )
    )

    with pytest.raises(FetchError):
        make_fetcher().fetch("https://example.com/imagem")


# Rejeita redirecionamento para IP privado.
@respx.mock
def test_redirect_to_private_ip_is_blocked() -> None:
    respx.get("https://example.com/edital").mock(
        return_value=httpx.Response(
            302,
            headers={"location": "https://insecure.test/segredo"},
        )
    )

    with pytest.raises(UrlPolicyError):
        make_fetcher(
            address_by_host={"insecure.test": "10.0.0.1"}
        ).fetch("https://example.com/edital")


# Respeita o limite de redirecionamentos.
@respx.mock
def test_redirect_limit() -> None:
    respx.get("https://example.com/edital").mock(
        return_value=httpx.Response(
            302,
            headers={"location": "https://example.com/outro"},
        )
    )

    with pytest.raises(FetchError):
        make_fetcher(max_redirects=0).fetch("https://example.com/edital")


# Converte timeout de rede em FetchError.
@respx.mock
def test_fetch_timeout() -> None:
    respx.get("https://example.com/edital").mock(
        side_effect=httpx.ConnectTimeout("timeout")
    )

    with pytest.raises(FetchError):
        make_fetcher().fetch("https://example.com/edital")


# Rejeita resposta vazia.
@respx.mock
def test_fetch_rejects_empty_content() -> None:
    respx.get("https://example.com/edital").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"",
        )
    )

    with pytest.raises(FetchError):
        make_fetcher().fetch("https://example.com/edital")


# Garante que o domínio do fetch é o mesmo da URL validada.
@respx.mock
def test_fetch_preserves_final_url() -> None:
    respx.get("https://example.com/edital").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<html>ok</html>",
        )
    )

    resource = make_fetcher().fetch("https://example.com/edital")

    assert urlparse(resource.final_url).hostname == "example.com"
