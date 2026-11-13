# Download de páginas HTML e PDFs com validação de segurança.

from __future__ import annotations

from urllib.parse import urljoin, urlparse

import httpx
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.browser.browser_manager import BrowserLaunchError, BrowserManager
from app.config import Settings, get_settings
from app.ingestion.models import FetchedResource
from app.security.url_policy import UrlPolicy, UrlPolicyError


# Erro lançado quando o download ou a validação falha.
class FetchError(RuntimeError):
    pass


# Tipos de conteúdo aceitos pelo pipeline.
ALLOWED_CONTENT_TYPES = {
    "text/html",
    "application/xhtml+xml",
    "application/pdf",
}


# Normaliza o Content-Type removendo parâmetros.
def normalize_content_type(value: str | None) -> str:
    if not value:
        return ""
    return value.split(";", 1)[0].strip().lower()


# Detecta o tipo real do recurso a partir do cabeçalho e dos bytes.
def detect_content_type(content: bytes, declared: str | None) -> str:
    if content.startswith(b"%PDF-"):
        return "application/pdf"

    normalized = normalize_content_type(declared)
    if normalized in ALLOWED_CONTENT_TYPES:
        return normalized

    if normalized in {"", "application/octet-stream", "binary/octet-stream"} and content.lstrip().startswith(
        (b"<!doctype", b"<html", b"<")
    ):
        return "text/html"

    return normalized


# Verifica se o tipo detectado pode ser processado.
def ensure_supported_content_type(content_type: str) -> None:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise FetchError(
            "Tipo de conteúdo não suportado: "
            f"{content_type or 'desconhecido'}. Use HTML ou PDF."
        )


# Verifica se o recurso é um PDF.
def is_pdf_resource(content: bytes, content_type: str) -> bool:
    return content.startswith(b"%PDF-") or content_type == "application/pdf"


# Baixa recursos estáticos por HTTP com redirecionamentos manuais.
class HttpSourceFetcher:
    def __init__(
        self,
        settings: Settings | None = None,
        policy: UrlPolicy | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.policy = policy or UrlPolicy(self.settings)

    # Baixa a URL respeitando tamanho, redirects e política de rede.
    def fetch(self, url: str) -> FetchedResource:
        timeout = httpx.Timeout(self.settings.fetch_timeout)
        headers = {"User-Agent": self.settings.fetch_user_agent}
        current_url = self.policy.validate(url).url

        try:
            with httpx.Client(
                follow_redirects=False,
                timeout=timeout,
                trust_env=False,
            ) as client:
                for redirect_count in range(self.settings.max_redirects + 1):
                    validated = self.policy.validate(current_url)
                    with client.stream(
                        "GET",
                        validated.url,
                        headers=headers,
                    ) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            if redirect_count >= self.settings.max_redirects:
                                raise FetchError("Número máximo de redirecionamentos excedido.")
                            location = response.headers.get("location")
                            if not location:
                                raise FetchError(
                                    "Redirecionamento sem cabeçalho Location."
                                )
                            current_url = urljoin(validated.url, location)
                            continue

                        if response.status_code >= 400:
                            raise FetchError(
                                f"A fonte retornou HTTP {response.status_code}."
                            )

                        declared_type = response.headers.get("content-type")
                        limit = (
                            self.settings.max_pdf_bytes
                            if _looks_like_pdf_url(validated.url, declared_type)
                            else self.settings.max_source_bytes
                        )
                        content = _read_limited(response, limit)
                        content_type = detect_content_type(content, declared_type)
                        ensure_supported_content_type(content_type)

                        return FetchedResource(
                            content=content,
                            content_type=content_type,
                            final_url=str(response.url),
                            status_code=response.status_code,
                            headers=dict(response.headers),
                        )
        except UrlPolicyError:
            raise
        except FetchError:
            raise
        except httpx.HTTPError as exc:
            raise FetchError(f"Falha ao baixar a fonte: {exc}") from exc

        raise FetchError("Não foi possível concluir o download.")


# Lê o corpo em blocos e interrompe ao ultrapassar o limite.
def _read_limited(response: httpx.Response, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0

    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > limit:
            raise FetchError(
                f"A fonte excede o limite de {limit} bytes."
            )
        chunks.append(chunk)

    content = b"".join(chunks)
    if not content:
        raise FetchError("A fonte retornou conteúdo vazio.")
    return content


# Usa heurística simples para escolher o limite antes da leitura.
def _looks_like_pdf_url(url: str, content_type: str | None) -> bool:
    normalized = normalize_content_type(content_type)
    return normalized == "application/pdf" or urlparse(url).path.lower().endswith(".pdf")


# Busca HTML renderizado com Playwright quando a página exige JavaScript.
class BrowserSourceFetcher:
    def __init__(
        self,
        settings: Settings | None = None,
        policy: UrlPolicy | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.policy = policy or UrlPolicy(self.settings)

    # Abre a página e devolve o HTML já renderizado.
    async def fetch(self, url: str) -> FetchedResource:
        validated = self.policy.validate(url)

        try:
            async with BrowserManager(settings=self.settings) as manager:
                page = await manager.new_page()
                response = await page.goto(
                    validated.url,
                    wait_until="domcontentloaded",
                )

                if response is not None and response.status >= 400:
                    raise FetchError(
                        f"A fonte retornou HTTP {response.status}."
                    )

                self.policy.validate(page.url)

                try:
                    await page.wait_for_load_state("networkidle", timeout=5_000)
                except PlaywrightTimeoutError:
                    pass

                html = await page.content()
                content_type = (
                    normalize_content_type(response.headers.get("content-type"))
                    if response is not None
                    else "text/html"
                )
                content = html.encode("utf-8")

                return FetchedResource(
                    content=content,
                    content_type=content_type or "text/html",
                    final_url=page.url,
                    status_code=response.status if response is not None else 200,
                    headers=dict(response.headers) if response is not None else {},
                )
        except (UrlPolicyError, FetchError):
            raise
        except BrowserLaunchError as exc:
            raise FetchError(str(exc)) from exc
        except Exception as exc:
            raise FetchError(f"Falha ao carregar a página no navegador: {exc}") from exc
