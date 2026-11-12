# Validação de URLs públicas para ingestão segura de editais.

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import Settings, get_settings

# Resolvedor de DNS injetável para testes.
Resolver = Callable[..., list[tuple]]


# Erro lançado quando uma URL viola a política de segurança.
class UrlPolicyError(ValueError):
    pass


# URL validada e endereços IP associados ao host.
@dataclass(frozen=True, slots=True)
class ValidatedUrl:
    url: str
    hostname: str
    resolved_ips: tuple[str, ...]


# Aplica as regras de HTTPS, domínio e SSRF.
class UrlPolicy:
    def __init__(
        self,
        settings: Settings | None = None,
        resolver: Resolver | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.resolver = resolver or socket.getaddrinfo

    # Valida esquema, host, domínio e endereços IP resolvidos.
    def validate(self, url: str) -> ValidatedUrl:
        candidate = url.strip()
        parsed = urlparse(candidate)
        scheme = parsed.scheme.lower()

        if scheme not in {"http", "https"}:
            raise UrlPolicyError("A URL deve usar HTTP ou HTTPS.")

        if scheme == "http" and not self.settings.allow_http:
            raise UrlPolicyError(
                "Apenas conexões HTTPS são permitidas. "
                "Defina ALLOW_HTTP=true para autorizar HTTP público."
            )

        hostname = (parsed.hostname or "").lower().rstrip(".")
        if not parsed.netloc or not hostname:
            raise UrlPolicyError("A URL deve conter um domínio válido.")

        if parsed.username or parsed.password:
            raise UrlPolicyError("A URL não pode conter credenciais embutidas.")

        self._validate_domain(hostname)

        try:
            port = parsed.port or (443 if scheme == "https" else 80)
        except ValueError as exc:
            raise UrlPolicyError("A URL contém uma porta inválida.") from exc

        resolved_ips = self._resolve(hostname, port)
        if not self.settings.allow_private_networks:
            for resolved_ip in resolved_ips:
                self._validate_public_ip(resolved_ip)

        return ValidatedUrl(
            url=parsed.geturl(),
            hostname=hostname,
            resolved_ips=resolved_ips,
        )

    # Confere listas de domínios permitidos e negados.
    def _validate_domain(self, hostname: str) -> None:
        blocked_suffixes = (
            ".localhost",
            ".local",
            ".internal",
            ".home.arpa",
        )
        if hostname == "localhost" or hostname.endswith(blocked_suffixes):
            raise UrlPolicyError("Hosts locais não são permitidos.")

        denied = self.settings.denied_domains
        if any(_domain_matches(hostname, domain) for domain in denied):
            raise UrlPolicyError(f"O domínio '{hostname}' está bloqueado.")

        allowed = self.settings.allowed_domains
        if allowed and not any(_domain_matches(hostname, domain) for domain in allowed):
            raise UrlPolicyError(f"O domínio '{hostname}' não está na lista permitida.")

    # Resolve o hostname e devolve os IPs encontrados.
    def _resolve(self, hostname: str, port: int) -> tuple[str, ...]:
        try:
            infos = self.resolver(hostname, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UrlPolicyError(
                f"Não foi possível resolver o domínio '{hostname}'."
            ) from exc

        resolved: list[str] = []
        for info in infos:
            if len(info) < 5:
                continue
            sockaddr = info[4]
            if not sockaddr:
                continue
            address = str(sockaddr[0]).split("%", 1)[0]
            if address and address not in resolved:
                resolved.append(address)

        if not resolved:
            raise UrlPolicyError(
                f"O domínio '{hostname}' não retornou endereços válidos."
            )

        return tuple(resolved)

    # Rejeita endereços privados, loopback, link-local e reservados.
    def _validate_public_ip(self, value: str) -> None:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise UrlPolicyError(f"Endereço IP inválido: {value}") from exc

        if not address.is_global:
            raise UrlPolicyError(
                f"Endereço IP não público bloqueado por segurança: {value}"
            )


# Confere se o host é igual ao domínio ou um subdomínio dele.
def _domain_matches(hostname: str, domain: str) -> bool:
    normalized = domain.strip().lower().rstrip(".")
    return hostname == normalized or hostname.endswith(f".{normalized}")
