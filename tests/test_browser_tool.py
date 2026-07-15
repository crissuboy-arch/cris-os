"""
Onda 2 / B7 — Browser Tool SOMENTE LEITURA (Playwright) + BrowserTarget.

Sem browser real (fake fetcher). Prova:
  - lê título/texto/links/imagens/screenshot;
  - URL inválida -> snapshot ok=False;
  - ações de escrita (click/fill/login/buy/publish/send) são RECUSADAS;
  - a classe NÃO tem métodos de escrita;
  - via Dispatcher+Gate: passo read-only passa sem confirmação e devolve TOOL.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.application import ExecutionDispatcher, TargetRegistry  # noqa: E402
from core.contracts.execution import DispatchContext, ExecutionTarget  # noqa: E402
from core.domain.execution import Effect, ExecutionType  # noqa: E402
from core.models import ExecutionStep  # noqa: E402
from tools.browser import BrowserTarget, BrowserTool  # noqa: E402


def fake_fetch(url, want_screenshot, screenshot_dir, **kw):
    return {
        "title": "Exemplo",
        "text": "conteudo da pagina",
        "links": ["https://a.com", "https://b.com"],
        "images": ["https://img/x.png"],
        "screenshot_path": (str(Path(screenshot_dir or ".") / "screenshot.png") if want_screenshot else ""),
    }


def _tool():
    return BrowserTool(fetcher=fake_fetch, screenshot_dir=".")


def test_read_extrai_dados():
    s = _tool().read("https://exemplo.com")
    assert s.ok and s.title == "Exemplo" and s.text == "conteudo da pagina"
    assert s.links == ["https://a.com", "https://b.com"] and s.images == ["https://img/x.png"]


def test_read_url_invalida():
    s = _tool().read("ftp://nope")
    assert s.ok is False and "URL inválida" in s.error


def test_screenshot():
    s = _tool().read("https://exemplo.com", want_screenshot=True)
    assert s.ok and s.screenshot_path.endswith("screenshot.png")


def test_classe_nao_tem_metodos_de_escrita():
    for m in ("click", "fill", "type", "login", "submit", "buy", "publish", "post", "send", "upload"):
        assert not hasattr(BrowserTool, m), f"BrowserTool não deveria ter '{m}'"


def test_target_cumpre_a_porta():
    assert isinstance(BrowserTarget(tool=_tool()), ExecutionTarget)


def _disp():
    return ExecutionDispatcher(TargetRegistry().register(BrowserTarget(tool=_tool())))


def test_target_read_only_passa_no_gate():
    step = ExecutionStep("browser", ExecutionType.TOOL, payload={"url": "https://x.com", "action": "text"})
    assert step.effect == Effect.READ_ONLY  # leitura não exige confirmação
    res = _disp().run([step], DispatchContext(session="s"))
    assert res[0].success and res[0].type == ExecutionType.TOOL and res[0].output == "conteudo da pagina"


def test_target_recusa_acoes_de_escrita():
    for acao in ("click", "fill", "login", "buy", "publish", "send"):
        step = ExecutionStep("browser", ExecutionType.TOOL, payload={"url": "https://x.com", "action": acao})
        res = _disp().run([step], DispatchContext(session="s"))
        assert res[0].success is False and "SOMENTE LEITURA" in res[0].output, acao


def test_target_acao_desconhecida():
    step = ExecutionStep("browser", ExecutionType.TOOL, payload={"url": "https://x.com", "action": "xpto"})
    res = _disp().run([step], DispatchContext(session="s"))
    assert res[0].success is False and "desconhecida" in res[0].output


if __name__ == "__main__":
    test_read_extrai_dados()
    test_read_url_invalida()
    test_screenshot()
    test_classe_nao_tem_metodos_de_escrita()
    test_target_cumpre_a_porta()
    test_target_read_only_passa_no_gate()
    test_target_recusa_acoes_de_escrita()
    test_target_acao_desconhecida()
    print("OK - test_browser_tool")
