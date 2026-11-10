# Controle do ciclo de vida do navegador Playwright.

from __future__ import annotations

import logging

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Route,
    async_playwright,
)

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


# Erro lançado quando o navegador não pode ser iniciado.
class BrowserLaunchError(RuntimeError):
    pass


# Gerencia a inicialização e o encerramento do Chromium.
class BrowserManager:
    # Permite sobrescrever a configuração em testes.
    def __init__(
        self,
        settings: Settings | None = None,
        headless: bool | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.headless = self.settings.headless if headless is None else headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # Bloqueia qualquer requisição HTTP não criptografada.
    async def _block_insecure_request(self, route: Route) -> None:
        request_url = route.request.url

        if request_url.startswith("http://"):
            logger.warning("Requisição HTTP bloqueada por segurança: %s", request_url)
            await route.abort("blockedbyclient")
            return

        await route.continue_()

    # Inicia o Playwright, o Chromium e o contexto.
    async def start(self) -> None:
        if self._browser is not None:
            return

        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless
            )
            self._context = await self._browser.new_context()
            timeout_ms = max(1, self.settings.execution_timeout) * 1000
            self._context.set_default_timeout(timeout_ms)
            await self._context.route("**/*", self._block_insecure_request)
        except Exception as exc:
            await self.close()
            raise BrowserLaunchError(
                "Não foi possível iniciar o Chromium. "
                "Execute: playwright install chromium"
            ) from exc

        logger.info("Navegador iniciado em modo headless=%s.", self.headless)

    # Cria ou devolve a página atual.
    async def new_page(self) -> Page:
        await self.start()

        if self._context is None:
            raise RuntimeError("O contexto do navegador não foi inicializado.")

        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()

        return self._page

    # Encerra página, contexto, navegador e Playwright.
    async def close(self) -> None:
        if self._page is not None and not self._page.is_closed():
            try:
                await self._page.close()
            except Exception:
                logger.debug("Falha ao fechar a página.", exc_info=True)
        self._page = None

        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                logger.debug("Falha ao fechar o contexto.", exc_info=True)
        self._context = None

        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                logger.debug("Falha ao fechar o navegador.", exc_info=True)
        self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                logger.debug("Falha ao encerrar o Playwright.", exc_info=True)
        self._playwright = None

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
