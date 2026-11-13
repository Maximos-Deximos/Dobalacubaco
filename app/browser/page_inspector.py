# Navegação e inspeção estrutural da página.

from __future__ import annotations

from urllib.parse import urlparse

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.config import Settings, get_settings
from app.schemas.form import PageSnapshot


# Erro lançado quando a URL não pode ser usada.
class InvalidUrlError(ValueError):
    pass


# Erro lançado quando a navegação falha.
class NavigationError(RuntimeError):
    pass


# Valida a URL e exige conexão criptografada com HTTPS.
def validate_url(url: str) -> str:
    candidate = url.strip()
    parsed = urlparse(candidate)

    if parsed.scheme != "https":
        raise InvalidUrlError(
            "Apenas conexões HTTPS são permitidas para evitar ataques de MITM."
        )

    if not parsed.netloc or not parsed.hostname:
        raise InvalidUrlError("A URL deve conter um domínio válido.")

    if parsed.username or parsed.password:
        raise InvalidUrlError("A URL não pode conter credenciais embutidas.")

    return parsed.geturl()


# Inspeciona a página principal e devolve metadados básicos.
class PageInspector:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # Navega para a URL e devolve o retrato da página.
    async def navigate(self, page: Page, url: str) -> PageSnapshot:
        safe_url = validate_url(url)

        try:
            response = await page.goto(safe_url, wait_until="domcontentloaded")
        except Exception as exc:
            raise NavigationError(
                f"Falha ao navegar para {safe_url}: {exc}"
            ) from exc

        if not page.url.startswith("https://"):
            raise NavigationError(
                "A navegação terminou em uma URL não criptografada e foi recusada."
            )

        if response is not None and response.status >= 400:
            raise NavigationError(
                f"A página retornou HTTP {response.status}: {safe_url}"
            )

        settle_timeout = min(5_000, max(1, self.settings.execution_timeout) * 1000)
        try:
            await page.wait_for_load_state("networkidle", timeout=settle_timeout)
        except PlaywrightTimeoutError:
            pass

        return await self.inspect(page)

    # Extrai título, formulários e iframes da página carregada.
    async def inspect(self, page: Page) -> PageSnapshot:
        title = (await page.title()).strip()
        form_count = await page.locator("form").count()

        iframe_urls = [
            frame.url
            for frame in page.frames
            if frame != page.main_frame
            and frame.url
            and frame.url != "about:blank"
        ]

        warnings: list[str] = []
        if iframe_urls:
            warnings.append(
                "A página contém iframes; frames compatíveis também serão inspecionados."
            )

        return PageSnapshot(
            url=page.url,
            title=title,
            form_count=form_count,
            iframe_urls=iframe_urls,
            warnings=warnings,
        )
