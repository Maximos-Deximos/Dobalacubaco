# Testes da política de navegação exclusivamente HTTPS.

import pytest

from app.browser.page_inspector import (
    InvalidUrlError,
    NavigationError,
    PageInspector,
    validate_url,
)
from app.main import main


# Aceita apenas URLs HTTPS válidas.
def test_validate_url_accepts_https() -> None:
    assert (
        validate_url("https://example.com/forms/apply")
        == "https://example.com/forms/apply"
    )


# Rejeita HTTP para impedir interceptação por MITM.
def test_validate_url_rejects_http() -> None:
    with pytest.raises(InvalidUrlError):
        validate_url("http://example.com/forms/apply")


# Rejeita esquemas que não sejam HTTPS.
@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/form",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "data:text/html,teste",
    ],
)
def test_validate_url_rejects_other_schemes(url: str) -> None:
    with pytest.raises(InvalidUrlError):
        validate_url(url)


# Rejeita URLs sem domínio ou com credenciais embutidas.
@pytest.mark.parametrize(
    "url",
    [
        "https:///form",
        "https://user:senha@example.com/form",
    ],
)
def test_validate_url_rejects_unsafe_parts(url: str) -> None:
    with pytest.raises(InvalidUrlError):
        validate_url(url)


# Confere que o comando inspect recusa HTTP antes de abrir o navegador.
def test_inspect_cli_rejects_http(capsys) -> None:
    assert main(["inspect", "http://example.com/form"]) == 1
    assert "HTTPS" in capsys.readouterr().err


# Bloqueia requisições HTTP disparadas pela própria página.
@pytest.mark.browser
async def test_browser_blocks_http_requests(forms_page) -> None:
    await forms_page.set_content(
        '<html><body><img src="http://insecure.test/pixel.png"></body></html>'
    )

    result = await forms_page.evaluate(
        """
        async () => {
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 3000);
          try {
            await fetch("http://insecure.test/data", { signal: controller.signal });
            return "carregou";
          } catch (error) {
            return "bloqueado";
          } finally {
            clearTimeout(timeout);
          }
        }
        """
    )

    assert result == "bloqueado"


# Confere que uma navegação HTTPS que redireciona para HTTP é recusada.
@pytest.mark.browser
async def test_navigation_rejects_https_to_http_redirect(page) -> None:
    async def redirect_route(route) -> None:
        await route.fulfill(
            status=302,
            headers={"location": "http://insecure.test/form"},
            body="",
        )

    await page.route("https://secure.test/**", redirect_route)

    with pytest.raises(NavigationError):
        await PageInspector().navigate(page, "https://secure.test/form")
