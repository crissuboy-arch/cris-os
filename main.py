"""
CRIS OS - Ponto de entrada.

Monta o sistema (via core/runtime.py) e inicia os canais. A lógica de montagem
fica no runtime; aqui só cuidamos de logs e de iniciar/parar com elegância.

Rode com:  python main.py
"""

import logging
import sys

from config.settings import settings
from core.runtime import StartupError, build


def configurar_logs() -> None:
    """Configura logs no console e em arquivo.

    Respostas de agentes (Fase 2+) podem conter emojis (ex.: "🔎", "🧩",
    "✅") -- o console do Windows, quando a saida e redirecionada (ex.:
    `python main.py > arquivo.log`), usa a codepage local (cp1252) em vez de
    UTF-8, e cp1252 nao representa a maioria dos emojis. Sem o
    `errors="replace"` abaixo, isso derrubava so a linha de log (nunca a
    resposta real do Telegram, que sempre usa UTF-8 via API) com um
    "Logging error" no stderr. `reconfigure` falha silenciosamente se o
    stream nao suportar (ex.: alguns runners de teste) -- sem problema, so
    nao aplica a tolerancia extra nesses casos.
    """
    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.LOGS_DIR / "cris_os.log", encoding="utf-8"),
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


def main() -> int:
    configurar_logs()
    logger = logging.getLogger("cris-os")
    logger.info("Iniciando o CRIS OS...")

    from config.settings import settings as s

    logger.info("ODS: %s (URL: %s | Fallback: %s)",
                "ativo" if s.ODS_ENABLED else "inativo",
                s.ODS_BASE_URL if s.ODS_ENABLED else "-",
                s.ODS_FALLBACK_PROVIDER if s.ODS_ENABLED else "-")

    if not s.REQUIRE_LLM_ON_STARTUP:
        logger.warning(
            "REQUIRE_LLM_ON_STARTUP=false: iniciando mesmo se nenhum LLM responder "
            "(agentes com ferramenta deterministica, ex.: scalaflow_intel, funcionam sem LLM)."
        )

    try:
        app = build(check_llm=s.REQUIRE_LLM_ON_STARTUP)
    except StartupError as exc:
        logger.error("Nao foi possivel iniciar:\n%s", exc)
        return 1

    ods_status = ""
    if app.ods_client:
        ods_status = " | ODS: " + ("online" if app.ods_client.is_online() else "offline")

    logger.info("Tudo pronto! Abra o Telegram e fale com o seu bot.%s (Ctrl+C para parar)", ods_status)

    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("CRIS OS encerrado. Ate logo, Cris!")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
