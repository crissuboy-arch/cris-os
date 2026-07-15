"""
Caracterização (Onda 1 / B0) — runtime.build() offline.
Monta o sistema sem rede (check_llm=False) num .db temporário e confere a saída.
Protege o B1 (limpeza do runtime) e o B4/B7 (mudanças no composition root).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import core.runtime as runtime  # noqa: E402
from config.settings import settings  # noqa: E402


def test_build_offline(tmp_path: Path):
    old_token, old_db = settings.TELEGRAM_BOT_TOKEN, settings.DB_PATH
    try:
        settings.TELEGRAM_BOT_TOKEN = "test:token"
        settings.DB_PATH = tmp_path / "cris_os.db"
        app = runtime.build(check_llm=False)
        assert app.channels and app.channels[0].name == "telegram"
        assert app.skills is not None and len(app.skills.all()) == 5
        assert [s.name for s in app.skills.enabled()] == ["session-handoff"]
    finally:
        settings.TELEGRAM_BOT_TOKEN, settings.DB_PATH = old_token, old_db


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        test_build_offline(Path(d))
    print("OK - test_runtime_build")
