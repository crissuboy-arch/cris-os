"""
BrowserTool — navegador SOMENTE LEITURA (Playwright headless).

Abre uma URL e extrai título, texto, links, imagens e screenshot. Por DESIGN não
existe clicar, preencher, login, comprar, publicar ou enviar — esses métodos não
estão na classe. Qualquer navegação é read-only (goto + leitura + screenshot).

O Playwright é importado de forma LAZY (só quando realmente navega), então
construir/registrar a ferramenta não exige o pacote instalado. Para uso real:
  pip install playwright  &&  python -m playwright install chromium

A busca da página é injetável (`fetcher`) — assim os testes rodam sem browser.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PageSnapshot:
    """Resultado de uma leitura de página (read-only)."""

    url: str
    title: str = ""
    text: str = ""
    links: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    screenshot_path: str = ""
    ok: bool = True
    error: str = ""


def _is_http(url) -> bool:
    return isinstance(url, str) and url.lower().startswith(("http://", "https://"))


def _playwright_fetch(url: str, want_screenshot: bool, screenshot_dir: str | None,
                      timeout_ms: int = 15000) -> dict:
    """Navega read-only com Playwright e devolve os dados da página."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:  # pragma: no cover - depende do ambiente
        raise RuntimeError(
            "Playwright não instalado. Rode: pip install playwright && "
            "python -m playwright install chromium"
        ) from e

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            out = {
                "title": page.title() or "",
                "text": (page.inner_text("body") or "")[:20000],
                "links": page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)"),
                "images": page.eval_on_selector_all("img[src]", "els => els.map(e => e.src)"),
                "screenshot_path": "",
            }
            if want_screenshot:
                base = Path(screenshot_dir or tempfile.mkdtemp())
                base.mkdir(parents=True, exist_ok=True)
                path = str(base / "screenshot.png")
                page.screenshot(path=path)
                out["screenshot_path"] = path
            return out
        finally:
            browser.close()


class BrowserTool:
    """Navegador SOMENTE LEITURA. Abre URL e extrai título/texto/links/imagens/screenshot.

    NÃO clica, NÃO preenche, NÃO faz login, NÃO compra, NÃO publica, NÃO envia —
    esses métodos simplesmente não existem aqui.
    """

    def __init__(self, fetcher=None, screenshot_dir: str | None = None) -> None:
        self._fetch = fetcher or _playwright_fetch
        self._shot_dir = screenshot_dir

    def read(self, url: str, want_screenshot: bool = False) -> PageSnapshot:
        """Abre a URL (read-only) e devolve um PageSnapshot."""
        if not _is_http(url):
            return PageSnapshot(url=str(url), ok=False, error="URL inválida (use http:// ou https://).")
        try:
            d = self._fetch(url, want_screenshot, self._shot_dir)
        except Exception as e:  # noqa: BLE001 - erro de navegação vira snapshot inválido
            return PageSnapshot(url=url, ok=False, error=str(e))
        return PageSnapshot(
            url=url,
            title=d.get("title", ""),
            text=d.get("text", ""),
            links=list(d.get("links", []) or []),
            images=list(d.get("images", []) or []),
            screenshot_path=d.get("screenshot_path", "") or "",
            ok=True,
        )
