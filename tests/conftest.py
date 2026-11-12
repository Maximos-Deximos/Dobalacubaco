# Fixtures compartilhadas para testes com banco isolado e navegador.

from pathlib import Path
from urllib.parse import urlparse

import pytest
import pytest_asyncio

from app.browser.browser_manager import BrowserLaunchError, BrowserManager
from app.config import get_settings
from app.memory.database import reset_engine

FORMS_DIR = Path(__file__).parent / "fixtures" / "forms"
GOOGLE_FORMS_FIXTURE = FORMS_DIR / "google_forms.html"


# Lê uma fixture HTML como texto.
def _fixture_html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# Registra uma rota HTTPS que serve HTML local.
async def _serve_html(route, path: Path) -> None:
    await route.fulfill(
        status=200,
        content_type="text/html; charset=utf-8",
        body=_fixture_html(path),
    )


# Cria um banco SQLite temporário e limpa o cache de configuração.
@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    reset_engine()

    yield database_url

    reset_engine()
    get_settings.cache_clear()


# Inicia um navegador headless e o encerra ao final do teste.
@pytest_asyncio.fixture
async def browser_manager():
    manager = BrowserManager(headless=True)

    try:
        await manager.start()
    except BrowserLaunchError as exc:
        await manager.close()
        pytest.skip(str(exc))

    try:
        yield manager
    finally:
        await manager.close()


# Cria uma página limpa para cada teste de navegador.
@pytest_asyncio.fixture
async def page(browser_manager):
    return await browser_manager.new_page()


# Serve as fixtures HTML por URLs HTTPS simuladas.
@pytest_asyncio.fixture
async def forms_page(page):
    async def handle_route(route) -> None:
        path = urlparse(route.request.url).path.lstrip("/")
        target = FORMS_DIR / path

        if target.is_file():
            await route.fulfill(
                status=200,
                content_type="text/html; charset=utf-8",
                body=target.read_text(encoding="utf-8"),
            )
            return

        await route.fulfill(
            status=404,
            content_type="text/plain; charset=utf-8",
            body="not found",
        )

    await page.route("https://forms.test/**", handle_route)
    return page


# Serve o fixture do Google Forms em uma URL do domínio docs.google.com.
@pytest_asyncio.fixture
async def google_forms_page(page):
    async def handle_route(route) -> None:
        await _serve_html(route, GOOGLE_FORMS_FIXTURE)

    await page.route("https://docs.google.com/**", handle_route)
    return page


# Serve um site externo com o Google Forms dentro de um iframe.
@pytest_asyncio.fixture
async def embedded_google_form_page(page):
    async def handle_wrapper(route) -> None:
        path = urlparse(route.request.url).path.lstrip("/")
        target = FORMS_DIR / path
        if target.is_file():
            await _serve_html(route, target)
            return
        await route.fulfill(status=404, body="not found")

    async def handle_google(route) -> None:
        await _serve_html(route, GOOGLE_FORMS_FIXTURE)

    await page.route("https://forms.test/**", handle_wrapper)
    await page.route("https://docs.google.com/**", handle_google)
    return page
