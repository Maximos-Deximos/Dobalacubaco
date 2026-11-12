# Testes da política de URLs e proteção contra SSRF.

import socket
from dataclasses import replace

import pytest

from app.config import Settings
from app.security.url_policy import UrlPolicy, UrlPolicyError

PUBLIC_IP = "93.184.216.34"


# Cria uma política com DNS simulado.
def make_policy(
    address: str = PUBLIC_IP,
    *,
    settings: Settings | None = None,
) -> UrlPolicy:
    base = settings or Settings.from_env(env={})

    def resolver(hostname, port, **_kwargs):
        if ":" in address:
            return [
                (
                    socket.AF_INET6,
                    socket.SOCK_STREAM,
                    6,
                    "",
                    (address, port, 0, 0),
                )
            ]
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (address, port),
            )
        ]

    return UrlPolicy(base, resolver=resolver)


# Aceita HTTPS público.
def test_accepts_public_https() -> None:
    validated = make_policy().validate("https://example.com/edital")

    assert validated.url == "https://example.com/edital"
    assert validated.resolved_ips == (PUBLIC_IP,)


# Rejeita HTTP por padrão.
def test_rejects_http_by_default() -> None:
    with pytest.raises(UrlPolicyError):
        make_policy().validate("http://example.com/edital")


# Permite HTTP apenas com opt-in explícito.
def test_allows_http_with_opt_in() -> None:
    settings = replace(Settings.from_env(env={}), allow_http=True)

    validated = make_policy(settings=settings).validate("http://example.com/edital")

    assert validated.url == "http://example.com/edital"


# Rejeita credenciais embutidas e esquemas inválidos.
@pytest.mark.parametrize(
    "url",
    [
        "https://user:senha@example.com/edital",
        "ftp://example.com/edital",
        "file:///etc/passwd",
        "javascript:alert(1)",
    ],
)
def test_rejects_unsafe_url_parts(url: str) -> None:
    with pytest.raises(UrlPolicyError):
        make_policy().validate(url)


# Bloqueia hosts locais.
@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/edital",
        "https://app.localhost/edital",
        "https://servidor.local/edital",
        "https://servidor.internal/edital",
    ],
)
def test_rejects_local_hosts(url: str) -> None:
    with pytest.raises(UrlPolicyError):
        make_policy().validate(url)


# Bloqueia endereços não públicos resolvidos.
@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "192.168.1.10",
        "169.254.169.254",
        "0.0.0.0",
        "::1",
        "fc00::1",
    ],
)
def test_rejects_non_public_addresses(address: str) -> None:
    with pytest.raises(UrlPolicyError):
        make_policy(address).validate("https://example.com/edital")


# Permite redes privadas somente quando configurado.
def test_allows_private_network_with_opt_in() -> None:
    settings = replace(
        Settings.from_env(env={}),
        allow_private_networks=True,
    )

    validated = make_policy("10.0.0.1", settings=settings).validate(
        "https://example.com/edital"
    )

    assert validated.resolved_ips == ("10.0.0.1",)


# Aplica listas de domínios permitidos e negados.
def test_domain_lists() -> None:
    settings = replace(
        Settings.from_env(env={}),
        allowed_domains=("example.com",),
        denied_domains=("blocked.example.com",),
    )
    policy = make_policy(settings=settings)

    assert policy.validate("https://docs.example.com/edital").hostname == "docs.example.com"

    with pytest.raises(UrlPolicyError):
        policy.validate("https://outro.test/edital")

    with pytest.raises(UrlPolicyError):
        policy.validate("https://blocked.example.com/edital")


# Converte falhas de DNS em erro de política.
def test_dns_failure() -> None:
    settings = Settings.from_env(env={})

    def failing_resolver(*_args, **_kwargs):
        raise OSError("dns indisponível")

    policy = UrlPolicy(settings, resolver=failing_resolver)

    with pytest.raises(UrlPolicyError):
        policy.validate("https://example.com/edital")
