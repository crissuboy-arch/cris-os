"""
Preflight da Fase 1 — verificador read-only do CRIS OS.

Confere, sem subir o bot, se está tudo pronto para a Secretária responder no
Telegram. Roda ANTES (env/Ollama/modelo) e DEPOIS (banco/eventos/memória) do
primeiro `python main.py`. Não altera nada, não conecta integrações novas.

Uso:  python scripts/preflight.py
"""

import sqlite3
import sys
from pathlib import Path

# Console do Windows costuma usar cp1252; força UTF-8 para acentos não quebrarem.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001 - se não der, segue sem reconfigurar
    pass

# Permite rodar de qualquer pasta (adiciona a raiz do projeto ao path).
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import requests  # noqa: E402

from config.settings import settings  # noqa: E402

OK, WARN, NO = "[OK]", "[!!]", "[--]"


def _check_python() -> None:
    v = sys.version_info
    nivel = OK if v >= (3, 10) else WARN
    print(f"{nivel} Python {v.major}.{v.minor}.{v.micro} (recomendado 3.10+)")


def _check_env() -> bool:
    existe = (RAIZ / ".env").exists()
    print(f"{OK if existe else NO} arquivo .env "
          + ("encontrado" if existe else "NAO encontrado (copie de .env.example)"))
    problemas = settings.validate()
    if problemas:
        for p in problemas:
            print(f"{NO} config: {p}")
        return False
    print(f"{OK} TELEGRAM_BOT_TOKEN configurado")
    print(f"{OK if settings.TELEGRAM_ALLOWED_USER_ID else WARN} "
          f"TELEGRAM_ALLOWED_USER_ID "
          + (settings.TELEGRAM_ALLOWED_USER_ID or "vazio (bot responde a qualquer um)"))
    return True


def _check_ollama() -> None:
    try:
        r = requests.get(f"{settings.OLLAMA_HOST}/api/tags", timeout=5)
        r.raise_for_status()
    except requests.RequestException:
        print(f"{NO} Ollama nao respondeu em {settings.OLLAMA_HOST} "
              f"(rode 'ollama serve')")
        return
    print(f"{OK} Ollama ativo em {settings.OLLAMA_HOST}")

    nomes = [m.get("name", "") for m in r.json().get("models", [])]
    alvo = settings.OLLAMA_MODEL
    tem = any(n == alvo or n.split(":")[0] == alvo or n.startswith(alvo) for n in nomes)
    if tem:
        print(f"{OK} modelo '{alvo}' instalado")
    else:
        print(f"{NO} modelo '{alvo}' NAO encontrado "
              f"(rode 'ollama pull {alvo}'). Instalados: {nomes or 'nenhum'}")


def _check_banco() -> None:
    db = settings.DB_PATH
    if not db.exists():
        print(f"{WARN} banco {db.name} ainda nao existe "
              f"(sera criado no primeiro 'python main.py')")
        return
    print(f"{OK} banco {db.name} criado")
    try:
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row

        def _conta(tabela: str) -> int:
            try:
                return conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            except sqlite3.OperationalError:
                return -1

        eventos = _conta("events")
        conversas = _conta("conversations")
        permanente = _conta("permanent_memory")
        projetos = _conta("project_memory")
        conn.close()

        print(f"{OK if eventos > 0 else WARN} Event Log: {max(eventos,0)} eventos")
        print(f"{OK if permanente > 0 else WARN} memoria permanente (L3): {max(permanente,0)} itens")
        print(f"{OK if projetos > 0 else WARN} memoria de projetos (L2): {max(projetos,0)} itens")
        print(f"{OK if conversas >= 0 else WARN} conversas (L1): {max(conversas,0)} mensagens")
    except sqlite3.Error as exc:
        print(f"{WARN} nao consegui ler o banco: {exc}")


def main() -> int:
    print("=== CRIS OS - Preflight da Fase 1 ===")
    print("\n-- Ambiente --")
    _check_python()
    env_ok = _check_env()
    print("\n-- Ollama (IA local) --")
    _check_ollama()
    print("\n-- Banco / memoria / eventos --")
    _check_banco()
    print("\nResumo: corrija os itens [--] antes de 'python main.py'. "
          "Itens [!!] sao avisos.")
    return 0 if env_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
